(function(){
  const catalog={
    en:{
      quota:{title:"OpenAI API balance is empty",detail:'Add credits in OpenAI API Platform Billing, then say “Hey Jarvis” again. Wake listening is ready.'},
      auth:{title:"OpenAI API key needs attention",detail:'Open Settings and replace the OpenAI API key, then say “Hey Jarvis” again.'},
      access:{title:"Realtime access was rejected",detail:"Check this API project's Realtime access and configuration, then try again."},
      rate:{title:"OpenAI API rate limit reached",detail:'Wait briefly, then say “Hey Jarvis” again.'},
      service:{title:"OpenAI Realtime is temporarily unavailable",detail:'Wait briefly, then say “Hey Jarvis” again. Wake listening is ready.'},
    },
    "zh-CN":{
      quota:{title:"OpenAI API 余额不足",detail:'请在 OpenAI API Platform Billing 中充值，然后再次说“Hey Jarvis”。本地唤醒监听已恢复。'},
      auth:{title:"OpenAI API 密钥需要处理",detail:'请打开设置并更换 OpenAI API 密钥，然后再次说“Hey Jarvis”。'},
      access:{title:"Realtime 访问被拒绝",detail:"请检查这个 API 项目的 Realtime 权限和配置，然后重试。"},
      rate:{title:"已达到 OpenAI API 速率限制",detail:'请稍等片刻，然后再次说“Hey Jarvis”。'},
      service:{title:"OpenAI Realtime 暂时不可用",detail:'请稍等片刻，然后再次说“Hey Jarvis”。本地唤醒监听已恢复。'},
    },
  };
  function category(diagnostic){
    if(!diagnostic||typeof diagnostic!=="object"||diagnostic.reason!=="webrtc_negotiation_failed")return null;
    const status=diagnostic.upstreamHttpStatus,type=diagnostic.errorType,code=diagnostic.errorCode;
    if(code==="credit_balance_exhausted"||type==="insufficient_quota")return "quota";
    if(status===401||code==="invalid_api_key"||type==="authentication_error")return "auth";
    if(status===400||status===403||status===404)return "access";
    if(status===429)return "rate";
    if(Number.isInteger(status)&&status>=500&&status<=599)return "service";
    return null;
  }
  function guidance(locale,diagnostic){
    const key=category(diagnostic);if(!key)return null;
    const language=locale==="zh-CN"?"zh-CN":"en",entry=catalog[language][key];
    return Object.freeze({category:key,title:entry.title,detail:entry.detail});
  }
  function preserveDuringAvailability(uiState,availability,armed,hasSession,diagnostic){
    return uiState==="error"&&availability==="wake_listening"&&armed===true&&hasSession===false&&guidance("en",diagnostic)!==null;
  }
  globalThis.HeyJarvisFailureGuidance=Object.freeze({guidance,preserveDuringAvailability});
})();
