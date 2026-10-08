import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import './studio.css';
import './save-extras.css';
class ErrorBoundary extends React.Component {
  state={error:null};
  static getDerivedStateFromError(error){return {error};}
  render(){return this.state.error?<main className="recovery"><h1>工作台暂时没有打开</h1><p>已保存的本地草稿仍在，刷新后可以恢复。</p><button onClick={()=>location.reload()}>重新打开</button><a href="/">返回此刻</a></main>:this.props.children;}
}
createRoot(document.getElementById('studio-root')).render(<ErrorBoundary><App/></ErrorBoundary>);
