export const diaryGroups = [
  {id:'mood', title:'心情', options:[['calm','平静','水面与小舟'],['happy','开心','花束与阳光'],['excited','兴奋','飞起的纸飞机'],['missing','思念','信封与远方灯火'],['sad','低落','雨窗与一朵花'],['tired','疲惫','靠枕与一杯茶'],['hopeful','期待','初升太阳与嫩芽'],['nostalgic','怀念','旧相片与唱片']]},
  {id:'weather', title:'天气', options:[['sunny','晴天','阳光与白云'],['cloudy','多云','层叠云朵'],['rainy','下雨','雨滴与雨伞'],['snowy','下雪','雪花与小屋'],['foggy','有雾','薄雾中的树'],['windy','有风','风中的叶片'],['night','夜晚','月亮与星光']]},
  {id:'activity', title:'状态', options:[['work','工作','桌面与台灯'],['study','学习','书本与铅笔'],['walk','散步','小路与步履'],['hike','徒步','山峦与背包'],['date','约会','双人咖啡与花'],['travel','旅行','行李箱与远方'],['commute','通勤','车窗与沿途风景'],['home','独处','窗边扶手椅'],['exercise','运动','运动鞋与水壶'],['gathering','聚会','圆桌与小串灯']]},
];
export const blankDiary = {mood:'',weather:'',activity:'',moodOther:'',weatherOther:'',activityOther:'',prompt:'',title:'',notes:'',images:[],existingImages:[],includeLocation:false,location:'',lat:null,lng:null};
export const diaryValue = (diary = blankDiary, key) => diary[key] === 'other' ? (diary[key+'Other']||'').trim() : diaryGroups.find(group=>group.id===key)?.options.find(([id])=>id===diary[key])?.[1] || '';
export function diaryFromMemory(memory) {
  const diary = {...blankDiary,prompt:memory?.music_prompt || '',title:memory?.title||'',notes:memory?.notes||'',existingImages:memory?.images||[],location:memory?.location||'',lat:memory?.lat??null,lng:memory?.lng??null,includeLocation:memory?.lat!=null};
  for(const group of diaryGroups) {
    const value = memory?.[group.id] || '';
    diary[group.id] = group.options.find(([id,label])=>id===value || label===value)?.[0] || (value ? 'other' : '');
    if(diary[group.id] === 'other') diary[group.id+'Other'] = value;
  }
  return diary;
}
