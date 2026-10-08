import io
import tempfile
import unittest
import wave
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from soundtrace_public import create_app
from tools.backup_public import backup


def audio(seconds=.2):
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b'\0\0' * int(16000 * seconds))
    return output.getvalue()


def photo():
    output = io.BytesIO()
    Image.new('RGB', (40, 50), '#59bdf0').save(output, format='PNG')
    return output.getvalue()


class PublicSiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.app = create_app(self.folder / 'data')
        self.alice = TestClient(self.app)
        self.bob = TestClient(self.app)
        self.guest = TestClient(self.app)
        for client, name in ((self.alice, 'alice'), (self.bob, 'bob')):
            r = client.post('/api/auth/register', json={'username': name, 'password': 'A-good-password-123'})
            self.assertEqual(r.status_code, 200, r.text)

    def tearDown(self):
        self.temp.cleanup()

    def save(self, client=None, share=False):
        r = (client or self.alice).post('/api/memories', data={'title': '海风', 'lat': '0', 'lng': '0', 'share': str(share).lower()},
            files=[('audio', ('audio.wav', audio(), 'audio/wav')), ('images', ('photo.png', photo(), 'image/png'))])
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()

    def test_diary_new_photos_location_opt_out_and_public_music(self):
        memory=self.save()
        result=self.alice.post('/api/memories/'+memory['id']+'/music',
            data={'title':'新的音乐日记','notes':'自己的话','include_location':'false'},
            files=[('music_audio',('mix.wav',audio(.5),'audio/wav')),('images',('new.png',photo(),'image/png'))])
        self.assertEqual(result.status_code,200,result.text)
        updated=result.json()
        self.assertEqual(len(updated['images']),2)
        self.assertIsNone(updated['lat'])
        self.assertIsNone(updated['lng'])
        self.assertEqual(updated['notes'],'自己的话')
        self.assertNotEqual(updated['cover_vinyl'],memory['cover_vinyl'])
        post=self.alice.post('/api/memories/'+memory['id']+'/publish').json()
        self.assertEqual(post['audio'],updated['music_audio'])
        self.assertEqual(self.guest.get('/'+post['audio']).status_code,200)
        self.assertEqual(self.guest.get('/'+memory['audio']).status_code,404)
        self.assertEqual(self.alice.post('/api/memories/'+memory['id']+'/publish').json()['id'],post['id'])
        remixed=self.alice.post('/api/memories/'+memory['id']+'/music',data={'notes':'更新后的日记'},files={'music_audio':('mix.wav',audio(.6),'audio/wav')}).json()
        self.assertEqual(self.guest.get('/'+post['audio']).status_code,200)
        synchronized=self.alice.post('/api/memories/'+memory['id']+'/publish').json()
        self.assertEqual(synchronized['id'],post['id'])
        self.assertEqual(synchronized['audio'],remixed['music_audio'])
        self.assertEqual(synchronized['text'],'更新后的日记')
        self.assertEqual(len(synchronized['images']),2)
        self.assertEqual(self.guest.get('/'+post['audio']).status_code,404)

    def test_letter_queue_matching_private_media_and_idempotence(self):
        memory=self.save()
        endpoint='/api/memories/'+memory['id']+'/send'
        self.assertEqual(self.bob.post(endpoint,json={}).status_code,404)
        sent=self.alice.post(endpoint,json={'kind':'tape','receive_mail':True,'allow_reuse':False})
        self.assertEqual(sent.status_code,200,sent.text)
        self.assertEqual(sent.json()['status'],'waiting')
        self.assertEqual(self.bob.get('/api/inbox').json()['items'],[])
        self.assertEqual(self.guest.get('/'+memory['audio']).status_code,404)
        bobmem=self.save(self.bob)
        reply=self.bob.post('/api/memories/'+bobmem['id']+'/send',json={'receive_mail':True})
        self.assertEqual(reply.json()['status'],'delivered')
        inbox=self.bob.get('/api/inbox').json()['items']
        self.assertEqual(len(inbox),1)
        self.assertEqual(inbox[0]['title'],'海风')
        self.assertNotIn('lat',inbox[0])
        self.assertNotIn('location',inbox[0])
        self.assertEqual(self.bob.get('/'+memory['audio']).status_code,200)
        self.assertEqual(self.guest.get('/'+memory['audio']).status_code,404)
        self.assertEqual(len(self.alice.get('/api/inbox').json()['items']),1)
        again=self.alice.post(endpoint,json={'kind':'tape','receive_mail':True})
        self.assertEqual(again.json()['id'],sent.json()['id'])
        self.assertEqual(len(self.alice.get('/api/exchange').json()['items']),1)
        self.alice.delete('/api/memories/'+memory['id'])
        self.assertEqual(self.bob.get('/api/inbox').json()['items'],[])
        self.assertEqual(self.bob.get('/'+memory['audio']).status_code,404)

    def test_saved_sample_reuse_isolation_replacement_and_restart(self):
        endpoint = '/api/studio/sample'
        self.assertEqual(self.guest.put(endpoint, files={'audio': ('x.wav', audio(1), 'audio/wav')}).status_code, 401)
        saved = self.alice.put(endpoint, data={'name': '河边测试'}, files={'audio': ('x.wav', audio(1), 'audio/wav')})
        self.assertEqual(saved.status_code, 200, saved.text)
        sample = saved.json()['sample']
        self.assertEqual(sample['name'], '河边测试')
        self.assertEqual(self.alice.get('/' + sample['audio']).content, audio(1))
        self.assertIsNone(self.bob.get(endpoint).json()['sample'])
        self.assertEqual(self.bob.get('/' + sample['audio']).status_code, 404)
        self.assertEqual(self.guest.get('/' + sample['audio']).status_code, 404)
        self.assertEqual(self.alice.get('/api/memories').json()['memories'], [])
        restarted = TestClient(create_app(self.folder / 'data'))
        restarted.cookies.update(self.alice.cookies)
        self.assertEqual(restarted.get(endpoint).json()['sample'], sample)
        for invalid in (b'not audio', audio(121), audio(.2)):
            rejected = self.alice.put(endpoint, files={'audio': ('invalid.wav', invalid, 'audio/wav')})
            self.assertEqual(rejected.status_code, 400, rejected.text)
            self.assertEqual(self.alice.get(endpoint).json()['sample'], sample)
        replaced = self.alice.put(endpoint, data={'name': '新示例'}, files={'audio': ('x.wav', audio(2), 'audio/wav')}).json()['sample']
        self.assertEqual(self.alice.get('/' + sample['audio']).status_code, 404)
        self.assertFalse((self.folder / 'data' / sample['audio'].removeprefix('outputs/')).exists())
        self.assertEqual(self.alice.get('/' + replaced['audio']).status_code, 200)
        self.bob.delete(endpoint)
        self.assertIsNotNone(self.alice.get(endpoint).json()['sample'])
        self.assertEqual(self.alice.delete(endpoint).status_code, 200)
        self.assertIsNone(self.alice.get(endpoint).json()['sample'])
        self.assertEqual(self.alice.get('/' + replaced['audio']).status_code, 404)
        self.assertFalse((self.folder / 'data' / replaced['audio'].removeprefix('outputs/')).exists())

    def test_private_collection_and_media_are_isolated(self):
        memory = self.save()
        self.assertEqual(len(self.alice.get('/api/memories').json()['memories']), 1)
        self.assertEqual(self.bob.get('/api/memories').json()['memories'], [])
        self.assertEqual(self.guest.get('/api/materials').json()['materials'], [])
        for ref in (memory['audio'], memory['images'][0], memory['cover_tape']):
            self.assertEqual(self.alice.get('/' + ref).status_code, 200)
            self.assertEqual(self.bob.get('/' + ref).status_code, 404)
            self.assertEqual(self.guest.get('/' + ref).status_code, 404)
        self.assertEqual(memory['lat'], 0)
        self.assertEqual(memory['lng'], 0)

    def test_diary_updates_original_memory_without_duplicating_or_losing_media(self):
        memory = self.save()
        endpoint = '/api/memories/' + memory['id'] + '/music'
        self.assertEqual(self.bob.get('/api/memories/' + memory['id']).status_code, 404)
        self.assertEqual(self.bob.post(endpoint, files={'music_audio':('mix.wav',audio(1),'audio/wav')}).status_code, 404)
        self.assertEqual(self.alice.post(endpoint, files={'music_audio':('mix.wav',b'bad','audio/wav')}).status_code, 400)
        saved = self.alice.post(endpoint, data={'mood':'期待','weather':'有风','activity':'徒步','music_prompt':'温暖的木吉他','music_style':'folk'}, files={'music_audio':('mix.wav',audio(1),'audio/wav')})
        self.assertEqual(saved.status_code, 200, saved.text)
        diary = saved.json()
        self.assertEqual(diary['id'], memory['id'])
        self.assertEqual(diary['audio'], memory['audio'])
        self.assertEqual(diary['images'], memory['images'])
        self.assertEqual(diary['lat'], 0)
        self.assertEqual(diary['activity'], '徒步')
        self.assertEqual(diary['music_prompt'], '温暖的木吉他')
        self.assertEqual(len(self.alice.get('/api/memories').json()['memories']), 1)
        self.assertEqual(self.alice.get('/api/materials').json()['materials'][0]['audio'], memory['audio'])
        vinyl = self.alice.get('/api/works').json()['works'][0]
        self.assertEqual(vinyl['audio'], diary['music_audio'])
        self.assertEqual(self.alice.get('/'+memory['audio']).content, audio())
        self.assertEqual(self.guest.get('/'+diary['music_audio']).status_code,404)
        replaced = self.alice.post(endpoint, files={'music_audio':('mix.wav',audio(2),'audio/wav')}).json()
        self.assertEqual(self.alice.get('/'+diary['music_audio']).status_code,404)
        self.assertEqual(self.alice.get('/'+replaced['music_audio']).content,audio(2))
        restored = TestClient(create_app(self.folder / 'data'))
        restored.cookies.update(self.alice.cookies)
        self.assertEqual(restored.get('/api/memories/'+memory['id']).json()['activity'],'徒步')

    def test_publish_exposes_only_selected_media_and_unpublish_revokes_it(self):
        memory = self.save(share=True)
        posts = self.guest.get('/api/feed').json()['posts']
        self.assertEqual(len(posts), 1)
        post = posts[0]
        self.assertFalse(post['mine'])
        self.assertNotIn('lat', post)
        self.assertEqual(post['author'], 'alice')
        self.assertEqual(self.guest.get('/' + memory['audio']).status_code, 200)
        self.assertEqual(self.guest.get('/' + memory['cover_vinyl']).status_code, 404)
        self.assertEqual(self.bob.delete('/api/feed/' + post['id']).status_code, 404)
        self.assertEqual(self.alice.delete('/api/feed/' + post['id']).status_code, 200)
        self.assertEqual(self.guest.get('/' + memory['audio']).status_code, 404)
        self.assertEqual(len(self.alice.get('/api/memories').json()['memories']), 1)

    def test_other_users_cannot_publish_or_delete_others_data(self):
        memory = self.save(share=True)
        self.assertEqual(self.bob.post('/api/feed', json={'text': '借来的', 'audio': memory['audio']}).status_code, 403)
        self.assertEqual(self.bob.delete('/api/memories/' + memory['id']).status_code, 404)
        self.assertEqual(self.bob.post('/api/memories/' + memory['id'] + '/publish').status_code, 404)

    def test_delete_removes_files_and_linked_public_posts(self):
        memory = self.save(share=True)
        self.assertEqual(self.alice.delete('/api/memories/' + memory['id']).status_code, 200)
        self.assertEqual(self.guest.get('/api/feed').json()['posts'], [])
        self.assertEqual(self.alice.get('/' + memory['audio']).status_code, 404)
        self.assertFalse((self.folder / 'data' / memory['audio'].removeprefix('outputs/')).exists())

    def test_restart_and_backup_preserve_saved_data(self):
        memory = self.save()
        restarted = TestClient(create_app(self.folder / 'data'))
        restarted.cookies.update(self.alice.cookies)
        self.assertEqual(restarted.get('/api/memories').json()['memories'][0]['id'], memory['id'])
        snapshot = backup(self.folder / 'data', self.folder / 'backups')
        restored = TestClient(create_app(snapshot))
        self.assertEqual(restored.get('/api/auth/session').json()['user'], None)
        self.assertEqual(restored.post('/api/auth/login', json={'username': 'alice', 'password': 'A-good-password-123'}).status_code, 200)
        self.assertEqual(restored.get('/' + memory['audio']).status_code, 200)

    def test_sessions_passwords_and_csrf(self):
        self.assertEqual(self.guest.post('/api/feed', json={'text': 'hello'}).status_code, 401)
        self.assertEqual(self.alice.post('/api/feed', headers={'Origin': 'https://evil.example'}, json={'text': 'attack'}).status_code, 403)
        old = TestClient(self.app)
        old.cookies.update(self.alice.cookies)
        r = self.alice.post('/api/auth/password', json={'current_password': 'A-good-password-123', 'password': 'Changed-password-456'})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(old.get('/api/auth/session').json()['user'])
        self.assertEqual(self.guest.post('/api/auth/login', json={'username': 'alice', 'password': 'A-good-password-123'}).status_code, 400)
        self.alice.post('/api/auth/logout')
        self.assertIsNone(self.alice.get('/api/auth/session').json()['user'])

    def test_https_cookie_and_host(self):
        secure = TestClient(create_app(self.folder / 'secure', 'https://sound.example'), base_url='https://sound.example')
        r = secure.post('/api/auth/register', json={'username': 'secure', 'password': 'A-good-password-123'})
        cookie = r.headers['set-cookie'].lower()
        self.assertIn('httponly', cookie)
        self.assertIn('secure', cookie)
        self.assertIn('samesite=lax', cookie)
        self.assertEqual(secure.get('/api/health', headers={'Host': 'evil.example'}).status_code, 400)

    def test_invalid_upload_does_not_leave_files_and_legacy_files_are_private(self):
        r = self.alice.post('/api/memories', data={'title': '坏图片'}, files=[('audio', ('audio.wav', audio())), ('images', ('bad.png', b'not-image'))])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.alice.get('/api/memories').json()['memories'], [])
        self.assertEqual(list((self.folder / 'data' / 'users').glob('*/*/audio.wav')), [])
        self.assertEqual(self.guest.get('/outputs/user.json').status_code, 404)
        self.assertEqual(self.guest.get('/outputs/works.json').status_code, 404)
        self.assertIn('声迹', self.guest.get('/?file=../../DEPLOY.md').text)
        self.assertEqual(self.alice.post('/api/feed', json={'text':'x', 'img':'assets/../../DEPLOY.md'}).status_code, 403)

    def test_real_profile_images_and_name_are_per_user(self):
        self.alice.post('/api/user', json={'name': '海边的我', 'logged_in': True})
        self.assertEqual(self.alice.get('/api/user').json()['name'], '海边的我')
        self.assertEqual(self.bob.get('/api/user').json()['name'], 'bob')
        r = self.alice.post('/api/user/background', files={'file': ('bg.png', photo(), 'image/png')})
        self.assertEqual(r.status_code, 200, r.text)
        ref = r.json()['background_img']
        self.assertEqual(self.alice.get('/' + ref).status_code, 200)
        self.assertEqual(self.bob.get('/' + ref).status_code, 404)

    def test_likes_and_replies_persist_and_cannot_be_deleted_by_other_users(self):
        self.save(share=True)
        pid = self.guest.get('/api/feed').json()['posts'][0]['id']
        self.assertEqual(self.bob.post(f'/api/feed/{pid}/like', json={'liked': True}).json()['like_count'], 1)
        self.assertEqual(self.bob.post(f'/api/feed/{pid}/like', json={'liked': True}).json()['like_count'], 1)
        post = self.bob.get('/api/feed').json()['posts'][0]
        self.assertTrue(post['liked'])
        self.assertEqual(post['like_count'], 1)
        cid = self.bob.post(f'/api/feed/{pid}/comments', json={'text': '这阵风很好听'}).json()['id']
        comments = self.guest.get(f'/api/feed/{pid}/comments').json()['comments']
        self.assertEqual(comments[0]['author'], 'bob')
        self.assertEqual(comments[0]['text'], '这阵风很好听')
        self.assertEqual(self.alice.delete('/api/comments/' + cid).status_code, 404)
        self.assertEqual(self.bob.delete('/api/comments/' + cid).status_code, 200)
        self.alice.delete('/api/feed/' + pid)
        self.assertEqual(self.bob.post(f'/api/feed/{pid}/like', json={'liked': True}).status_code, 404)

    def test_music_and_original_are_distinct_and_return_to_collection(self):
        r = self.alice.post('/api/memories', data={'title':'现场与旋律'},
            files=[('audio', ('raw.wav', audio(), 'audio/wav')), ('music_audio', ('mix.wav', audio(), 'audio/wav'))])
        self.assertEqual(r.status_code, 201, r.text)
        memory = r.json()
        tape = self.alice.get('/api/materials').json()['materials'][0]
        vinyl = self.alice.get('/api/works').json()['works'][0]
        self.assertEqual(tape['audio'], memory['audio'])
        self.assertEqual(vinyl['audio'], memory['music_audio'])
        self.assertNotEqual(tape['audio'], vinyl['audio'])
        self.assertEqual(self.bob.get('/' + vinyl['audio']).status_code, 404)


if __name__ == '__main__':
    unittest.main()
