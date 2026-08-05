(function(){
  const zh="zh-CN";
  const staticZh=new Map(Object.entries({
    "Open Settings":"打开设置",Settings:"设置",Ready:"就绪","Meet your voice assistant":"认识你的语音助手",
    "Enable hands-free audio once, then wake Jarvis with your voice.":"只需启用一次免手持音频，之后即可用语音唤醒 Jarvis。",
    "Voice controls":"语音控制","Enable voice assistant":"启用语音助手","End conversation":"结束对话",
    "Wake phrase detection stays on this Mac. Conversation audio is sent only after wake.":"唤醒词检测始终留在这台 Mac 上。只有唤醒后才会发送对话音频。",
    "Resume voice assistant":"恢复语音助手",
  }));
  const states={en:{
    ready:{label:"Ready",title:"Meet your voice assistant",detail:"Enable hands-free audio once, then wake Jarvis with your voice."},
    "wake-ready":{label:"Wake listening",title:'Waiting for “Hey Jarvis”',detail:"Wake phrase detection stays on this Mac."},
    connecting:{label:"Connecting",title:"Getting ready",detail:"Conversation audio stays off until the secure session is ready."},
    listening:{label:"Listening",title:"I’m listening",detail:"Speak naturally — you can follow up or interrupt at any time."},
    thinking:{label:"Thinking",title:"Working on it",detail:"Jarvis is preparing a response."},speaking:{label:"Speaking",title:"Responding",detail:"You can interrupt at any time."},
    stopping:{label:"Ending",title:"Closing the conversation",detail:"Releasing the microphone and restoring local wake listening."},
    "resume-required":{label:"Resume required",title:"Voice assistant paused",detail:"Open Settings or restart Hey Jarvis to restore voice listening."},
    error:{label:"Needs attention",title:"Jarvis couldn’t continue",detail:"Wake listening is safe. Try again or open Settings for recovery."},
  },"zh-CN":{
    ready:{label:"就绪",title:"认识你的语音助手",detail:"只需启用一次免手持音频，之后即可用语音唤醒 Jarvis。"},
    "wake-ready":{label:"正在等待唤醒",title:'等待“Hey Jarvis”',detail:"唤醒词检测始终留在这台 Mac 上。"},
    connecting:{label:"正在连接",title:"正在准备",detail:"安全会话就绪前不会发送对话音频。"},
    listening:{label:"正在聆听",title:"我在听",detail:"请自然说话，你可以继续追问或随时打断。"},
    thinking:{label:"正在思考",title:"正在处理",detail:"Jarvis 正在准备回答。"},speaking:{label:"正在回答",title:"正在回应",detail:"你可以随时打断。"},
    stopping:{label:"正在结束",title:"正在关闭对话",detail:"正在释放麦克风并恢复本地唤醒监听。"},
    "resume-required":{label:"需要恢复",title:"语音助手已暂停",detail:"请打开设置或重启 Hey Jarvis 以恢复语音监听。"},
    error:{label:"需要处理",title:"Jarvis 无法继续",detail:"唤醒监听处于安全状态。请重试或打开设置进行恢复。"},
  }};
  const detailsZh=new Map(Object.entries({"I can hear you.":"我能听到你。","Saying goodbye before returning to wake listening.":"正在告别，然后返回唤醒监听。","Playing the acknowledgement.":"正在播放回应语。","Connected securely. Waiting for the ready acknowledgement.":"安全连接已建立，正在等待回应语播放。","Secure transport connected. Finishing voice setup.":"安全传输已连接，正在完成语音设置。","Restoring local wake listening after system sleep…":"系统睡眠后正在恢复本地唤醒监听…"}));
  const originals=new WeakMap();function locale(value){return value===zh?zh:"en";}
  function apply(value){const resolved=locale(value);document.documentElement.lang=resolved;const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node;while((node=walker.nextNode())){if(!originals.has(node))originals.set(node,node.nodeValue);const original=originals.get(node),trimmed=original.trim();if(resolved!==zh||!staticZh.has(trimmed)){node.nodeValue=original;continue;}const start=original.indexOf(trimmed);node.nodeValue=original.slice(0,start)+staticZh.get(trimmed)+original.slice(start+trimmed.length);}for(const element of document.querySelectorAll("[aria-label], [title]"))for(const attribute of ["aria-label","title"]){if(!element.hasAttribute(attribute))continue;const key=attribute==="title"?"i18nTitle":"i18nAria";if(!element.dataset[key])element.dataset[key]=element.getAttribute(attribute);const original=element.dataset[key];element.setAttribute(attribute,resolved===zh&&staticZh.has(original)?staticZh.get(original):original);}}
  function detail(value,english){return locale(value)===zh?(detailsZh.get(english)||english):english;}
  function text(english){return locale(document.documentElement.lang)===zh?(staticZh.get(english)||english):english;}
  window.HeyJarvisI18n={locale,apply,states,detail,text};
})();
