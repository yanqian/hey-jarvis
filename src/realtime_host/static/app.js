"use strict";

const AUDIO_CONSTRAINTS={echoCancellation:{exact:true},noiseSuppression:true,autoGainControl:true,channelCount:1};
const REMOTE_AUDIO_VOLUME=0.1;
const INPUT_LEVEL_SAMPLE_INTERVAL_MS=100,INPUT_LEVEL_WINDOW_SAMPLES=5;
const KEEP_WARM_MICROPHONE=location.hash==="#smart-speaker-mode";
let armed=false,lastCommand=0,pc=null,dc=null,stream=null,warmStream=null,inputTrack=null,sessionId=null,sessionConfig=null,events=[],handoffTiming=null,sessionCreatedAt=null,dataChannelOpenedAt=null,transportReported=false,configurationReportStarted=false;
let levelContext=null,levelAnalyser=null,levelSource=null,levelTimer=null,levelSamples=[],assistantSpeaking=false;
let responseActive=false,turnResponsePending=false,farewellPending=false,farewellStarted=false,farewellCallId=null,farewellResponseActive=false;
let realtimeAcknowledgement=false,acknowledgementStarted=false,acknowledgementResponseActive=false;
let acknowledgementCaptureLabel=null,acknowledgementCapture=null,acknowledgementTranscript=null,remoteStream=null;
let cachedAcknowledgementUrl=null,cachedAcknowledgementPending=false,cachedAcknowledgementToken=0;
const hostId=crypto.randomUUID().replaceAll("-","");
const $=id=>document.getElementById(id);

const UI_STATES={
  ready:{label:"Ready",title:"Meet your voice assistant",detail:"Enable hands-free audio once, then wake Jarvis with your voice."},
  "wake-ready":{label:"Wake listening",title:'Waiting for “Hey Jarvis”',detail:"Wake phrase detection stays on this Mac."},
  connecting:{label:"Connecting",title:"Getting ready",detail:"Conversation audio stays off until the secure session is ready."},
  listening:{label:"Listening",title:"I’m listening",detail:"Speak naturally — you can follow up or interrupt at any time."},
  thinking:{label:"Thinking",title:"Working on it",detail:"Jarvis is preparing a response."},
  speaking:{label:"Speaking",title:"Responding",detail:"You can interrupt at any time."},
  stopping:{label:"Ending",title:"Closing the conversation",detail:"Releasing the microphone and restoring local wake listening."},
  "resume-required":{label:"Resume required",title:"Voice assistant paused",detail:"Open Settings or restart Hey Jarvis to restore voice listening."},
  error:{label:"Needs attention",title:"Jarvis couldn’t continue",detail:"Wake listening is safe. Try again or open Settings for recovery."},
};

function setUiState(state,detail=null){
  const presentation=UI_STATES[state]||UI_STATES.error;
  document.body.dataset.uiState=state in UI_STATES?state:"error";
  $("status-label").textContent=presentation.label;
  $("status-title").textContent=presentation.title;
  $("status-detail").textContent=detail||presentation.detail;
}
function configuredOutputVolume(){return Number.isFinite(sessionConfig?.output_volume)?sessionConfig.output_volume:REMOTE_AUDIO_VOLUME;}

function encodeMonoWav(chunks,sampleRate){
  const sampleCount=chunks.reduce((total,chunk)=>total+chunk.length,0),buffer=new ArrayBuffer(44+sampleCount*2),view=new DataView(buffer);
  const text=(offset,value)=>{for(let index=0;index<value.length;index++)view.setUint8(offset+index,value.charCodeAt(index));};
  text(0,"RIFF");view.setUint32(4,36+sampleCount*2,true);text(8,"WAVE");text(12,"fmt ");view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,sampleRate,true);view.setUint32(28,sampleRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,"data");view.setUint32(40,sampleCount*2,true);
  let offset=44;for(const chunk of chunks)for(const value of chunk){const bounded=Math.max(-1,Math.min(1,value));view.setInt16(offset,bounded<0?bounded*0x8000:bounded*0x7fff,true);offset+=2;}
  return buffer;
}
function base64FromBuffer(buffer){
  const bytes=new Uint8Array(buffer);let binary="";for(let offset=0;offset<bytes.length;offset+=0x8000)binary+=String.fromCharCode(...bytes.subarray(offset,offset+0x8000));return btoa(binary);
}
function createAcknowledgementCapture(mediaStream){
  const AudioContextClass=window.AudioContext||window.webkitAudioContext;if(!AudioContextClass)throw new Error("Web Audio capture is unavailable");
  const context=Reflect.construct(AudioContextClass,[]),source=context.createMediaStreamSource(mediaStream),processor=context.createScriptProcessor(4096,1,1),sink=context.createGain(),chunks=[];
  sink.gain.value=0;processor.onaudioprocess=event=>chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));source.connect(processor);processor.connect(sink);sink.connect(context.destination);context.resume().catch(()=>{});
  let closed=false;return {
    async finish(){if(closed)throw new Error("ACK capture already closed");closed=true;processor.onaudioprocess=null;try{source.disconnect();processor.disconnect();sink.disconnect();}catch{}await context.close();if(!chunks.length)throw new Error("ACK capture contains no samples");return encodeMonoWav(chunks,context.sampleRate);},
    abort(){if(closed)return;closed=true;processor.onaudioprocess=null;try{source.disconnect();processor.disconnect();sink.disconnect();}catch{}context.close().catch(()=>{});},
  };
}
function responseTranscript(response){
  for(const item of response?.output||[])for(const content of item?.content||[])if(typeof content?.transcript==="string")return content.transcript;return null;
}
async function uploadAcknowledgementCapture(){
  if(!acknowledgementCaptureLabel||!acknowledgementCapture)throw new Error("ACK capture was not initialized");
  const label=acknowledgementCaptureLabel,capture=acknowledgementCapture;acknowledgementCapture=null;
  const wav=await capture.finish();
  await post("/api/acknowledgement-capture/candidate",{label,transcript:acknowledgementTranscript,audio:base64FromBuffer(wav)});
}

async function prepareCachedAcknowledgement(settings){
  if(cachedAcknowledgementUrl){URL.revokeObjectURL(cachedAcknowledgementUrl);cachedAcknowledgementUrl=null;}
  const acknowledgement=settings?.acknowledgement;
  if(acknowledgement?.mode!=="cached")return;
  if(acknowledgement.url!=="/acknowledgement.wav"||!Number.isInteger(acknowledgement.duration_ms)||acknowledgement.duration_ms<500||acknowledgement.duration_ms>6000||typeof acknowledgement.sha256!=="string"||!/^[a-f0-9]{64}$/.test(acknowledgement.sha256))throw new Error("Cached acknowledgement metadata is invalid");
  const response=await fetch(acknowledgement.url,{cache:"no-store"});if(!response.ok)throw new Error("Cached acknowledgement is unavailable");
  const bytes=await response.arrayBuffer();if(bytes.byteLength<44||bytes.byteLength>1500000)throw new Error("Cached acknowledgement size is invalid");
  cachedAcknowledgementUrl=URL.createObjectURL(new Blob([bytes],{type:"audio/wav"}));
}
function resetCachedAcknowledgementPlayback(){
  cachedAcknowledgementToken+=1;cachedAcknowledgementPending=false;
  const audio=$("remoteAudio");audio.onended=null;audio.onerror=null;audio.pause();audio.removeAttribute("src");
}
async function attachRemoteAudio(){
  if(!remoteStream||cachedAcknowledgementPending)return;
  const audio=$("remoteAudio");audio.onended=null;audio.onerror=null;audio.pause();audio.removeAttribute("src");audio.srcObject=remoteStream;audio.volume=configuredOutputVolume();
  const playAttempt=audio.play();if(playAttempt)await playAttempt;log("remote_audio_track");
}
async function startCachedAcknowledgement(command){
  if(command.acknowledgement_mode!=="cached"||!cachedAcknowledgementUrl)throw new Error("Cached acknowledgement was not prepared");
  const expectedSession=command.session_id,token=++cachedAcknowledgementToken,audio=$("remoteAudio");cachedAcknowledgementPending=true;
  audio.pause();audio.srcObject=null;audio.src=cachedAcknowledgementUrl;audio.volume=configuredOutputVolume();audio.currentTime=0;
  const ended=new Promise((resolve,reject)=>{audio.onended=resolve;audio.onerror=()=>reject(new Error("Cached acknowledgement playback failed"));});
  await audio.play();
  if(token!==cachedAcknowledgementToken||sessionId!==expectedSession)return;
  await hostEvent("cached_ack_playback_started");
  await ended;
  if(token!==cachedAcknowledgementToken||sessionId!==expectedSession)return;
  cachedAcknowledgementPending=false;audio.onended=null;audio.onerror=null;
  await attachRemoteAudio();
  await hostEvent("cached_ack_playback_stopped");
}

function showEndControl(show){
  $("stop").hidden=!show;
  $("stop").disabled=!show;
}

function log(type,detail={}){events.push({at_ms:Math.round(performance.now()),type,...detail});events=events.slice(-100);}
async function post(path,payload={}){const response=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data.message||data.error);return data;}
async function hostEvent(type,detail={}){return post("/api/event",{type,session_id:sessionId,host_id:hostId,...detail});}
function renderSettings(_settings){}
async function preferStrongestEchoCancellation(track){
  const capabilities=typeof track.getCapabilities==="function"?track.getCapabilities():{};
  const advertised=Array.isArray(capabilities.echoCancellation)?capabilities.echoCancellation:[];
  const allSupported=advertised.includes("all");
  if(allSupported){
    try{
      await track.applyConstraints({...AUDIO_CONSTRAINTS,echoCancellation:{exact:"all"}});
      return {requested:"all",allSupported:true};
    }catch{}
  }
  await track.applyConstraints(AUDIO_CONSTRAINTS);
  return {requested:"true",allSupported};
}
function boundedDiagnosticValue(value){
  return typeof value==="string"&&/^[A-Za-z0-9_.:-]{1,100}$/.test(value)?value:null;
}
async function negotiationFailure(response){
  let payload=null;try{payload=await response.clone().json()}catch{}
  const providerError=payload&&typeof payload.error==="object"&&payload.error?payload.error:{};
  const detail={reason:"webrtc_negotiation_failed",httpStatus:response.status};
  const fields=[
    ["errorType",providerError.type],
    ["errorCode",providerError.code],
    ["requestId",response.headers.get("x-request-id")],
    ["retryAfter",response.headers.get("retry-after")],
    ["rateLimitRemainingRequests",response.headers.get("x-ratelimit-remaining-requests")],
    ["rateLimitRemainingTokens",response.headers.get("x-ratelimit-remaining-tokens")],
    ["rateLimitRemainingProjectTokens",response.headers.get("x-ratelimit-remaining-project-tokens")],
    ["rateLimitResetRequests",response.headers.get("x-ratelimit-reset-requests")],
    ["rateLimitResetTokens",response.headers.get("x-ratelimit-reset-tokens")],
    ["rateLimitResetProjectTokens",response.headers.get("x-ratelimit-reset-project-tokens")],
  ];
  for(const [key,value] of fields){const safe=boundedDiagnosticValue(value);if(safe!==null)detail[key]=safe;}
  const error=new Error(`WebRTC negotiation failed (${response.status})`);error.safeDiagnostic=detail;return error;
}
function flushInputLevels(){
  if(!levelSamples.length||!sessionId)return;
  const phase=levelSamples[0].phase;
  const rms=Math.max(...levelSamples.map(sample=>sample.rms));
  const peak=Math.max(...levelSamples.map(sample=>sample.peak));
  const sampleCount=levelSamples.length;levelSamples=[];
  hostEvent("input_level",{phase,rms:Number(rms.toFixed(4)),peak:Number(peak.toFixed(4)),sampleCount}).catch(()=>{});
}
function stopInputLevels(){
  if(levelTimer){clearInterval(levelTimer);levelTimer=null;}
  flushInputLevels();
  if(levelSource){try{levelSource.disconnect()}catch{}levelSource=null;}
  if(levelContext){levelContext.close().catch(()=>{});levelContext=null;}
  levelAnalyser=null;levelSamples=[];assistantSpeaking=false;
}
function startInputLevels(mediaStream,timing){
  stopInputLevels();
  timing.inputLevelsCleaned=performance.now();
  const AudioContextClass=window.AudioContext||window.webkitAudioContext;
  if(!AudioContextClass){
    timing.audioContextCreated=timing.analyserReady=timing.mediaStreamSourceCreated=timing.sourceConnected=timing.audioAnalysisReady=performance.now();
    return;
  }
  levelContext=new AudioContextClass();timing.audioContextCreated=performance.now();
  levelAnalyser=levelContext.createAnalyser();
  levelAnalyser.fftSize=1024;levelAnalyser.smoothingTimeConstant=0;
  timing.analyserReady=performance.now();
  levelSource=levelContext.createMediaStreamSource(mediaStream);timing.mediaStreamSourceCreated=performance.now();
  levelSource.connect(levelAnalyser);timing.sourceConnected=performance.now();
  levelContext.resume().catch(()=>{});
  const samples=new Float32Array(levelAnalyser.fftSize);
  levelTimer=setInterval(()=>{
    if(!levelAnalyser||!sessionId)return;
    levelAnalyser.getFloatTimeDomainData(samples);
    let sumSquares=0,peak=0;
    for(const value of samples){sumSquares+=value*value;peak=Math.max(peak,Math.abs(value));}
    const phase=assistantSpeaking?"remote_playback":"no_remote_playback";
    if(levelSamples.length&&levelSamples[0].phase!==phase)flushInputLevels();
    levelSamples.push({phase,rms:Math.sqrt(sumSquares/samples.length),peak});
    if(levelSamples.length>=INPUT_LEVEL_WINDOW_SAMPLES)flushInputLevels();
  },INPUT_LEVEL_SAMPLE_INTERVAL_MS);
  timing.audioAnalysisReady=performance.now();
}
function skipInputLevels(timing){
  const skippedAt=timing.microphoneReported;
  timing.inputLevelsCleaned=timing.audioContextCreated=timing.analyserReady=skippedAt;
  timing.mediaStreamSourceCreated=timing.sourceConnected=timing.audioAnalysisReady=skippedAt;
}

async function arm(){
  try{
    const [settingsResponse,warm]=await Promise.all([
      fetch("/api/realtime-settings",{cache:"no-store"}),
      navigator.mediaDevices.getUserMedia({audio:AUDIO_CONSTRAINTS}),
    ]);
    const safeSettings=await settingsResponse.json();if(!settingsResponse.ok)throw new Error(safeSettings.message||safeSettings.error);
    sessionConfig=safeSettings;
    await prepareCachedAcknowledgement(safeSettings);
    renderSettings(warm.getAudioTracks()[0]?.getSettings()||{});
    if(KEEP_WARM_MICROPHONE){warm.getAudioTracks().forEach(track=>{track.enabled=false;});warmStream=warm;}
    else warm.getTracks().forEach(track=>track.stop());
    const audio=$("remoteAudio");
    if(KEEP_WARM_MICROPHONE){audio.srcObject=warmStream;audio.volume=0;await audio.play();}
    else audio.volume=configuredOutputVolume();
    sessionId=null;await hostEvent("armed");armed=true;$("arm").disabled=true;$("arm").hidden=true;
    setUiState("wake-ready");log("armed");poll();
  }catch(error){releasePageMedia();sessionConfig=null;$("arm").disabled=false;$("arm").hidden=false;setUiState("error",`Voice setup failed: ${error.message}`);}
}

function elapsedMs(start,end){return Math.max(0,Math.round(end-start));}
function handoffTimingSummary(readyAt){
  const timing=handoffTiming;
  if(!timing||dataChannelOpenedAt===null||sessionCreatedAt===null)throw new Error("handoff timing is unavailable");
  if(dataChannelOpenedAt<timing.negotiationCompleted||sessionCreatedAt<dataChannelOpenedAt)throw new Error("Realtime readiness timing was misordered");
  const dataChannelOpenMs=elapsedMs(timing.negotiationCompleted,dataChannelOpenedAt);
  const sessionCreatedAfterDataChannelOpenMs=elapsedMs(dataChannelOpenedAt,sessionCreatedAt);
  const summary={
    command_to_token_ms:elapsedMs(timing.commandReceived,timing.tokenStarted),
    token_ms:elapsedMs(timing.tokenStarted,timing.tokenAcquired),
    microphone_ms:elapsedMs(timing.microphoneStarted,timing.microphoneAcquired),
    peer_setup_ms:elapsedMs(timing.microphoneAcquired,timing.negotiationStarted),
    microphone_reporting_ms:elapsedMs(timing.microphoneAcquired,timing.microphoneReported),
    audio_analysis_setup_ms:elapsedMs(timing.microphoneReported,timing.audioAnalysisReady),
    input_level_cleanup_ms:elapsedMs(timing.microphoneReported,timing.inputLevelsCleaned),
    audio_context_creation_ms:elapsedMs(timing.inputLevelsCleaned,timing.audioContextCreated),
    analyser_setup_ms:elapsedMs(timing.audioContextCreated,timing.analyserReady),
    media_stream_source_creation_ms:elapsedMs(timing.analyserReady,timing.mediaStreamSourceCreated),
    source_connection_ms:elapsedMs(timing.mediaStreamSourceCreated,timing.sourceConnected),
    monitor_startup_ms:elapsedMs(timing.sourceConnected,timing.audioAnalysisReady),
    peer_connection_setup_ms:elapsedMs(timing.audioAnalysisReady,timing.peerConnectionReady),
    offer_creation_ms:elapsedMs(timing.peerConnectionReady,timing.offerCreated),
    local_description_ms:elapsedMs(timing.offerCreated,timing.negotiationStarted),
    negotiation_ms:elapsedMs(timing.negotiationStarted,timing.negotiationCompleted),
    data_channel_open_ms:dataChannelOpenMs,
    session_created_after_data_channel_open_ms:sessionCreatedAfterDataChannelOpenMs,
    session_configuration_ms:dataChannelOpenMs+sessionCreatedAfterDataChannelOpenMs,
    total_browser_ready_ms:elapsedMs(timing.commandReceived,readyAt),
  };
  const topLevelPhases=["command_to_token_ms","token_ms","microphone_ms","peer_setup_ms","negotiation_ms","session_configuration_ms"];
  summary.total_browser_ready_ms=topLevelPhases.reduce((total,key)=>total+summary[key],0);
  return summary;
}

async function forwardToolCall(item){
  const result=await hostEvent("tool_call",{call_id:item.call_id,name:item.name,arguments:item.arguments});
  if(result.status==="farewell"){await requestFarewell(item.call_id);return true;}
  if(result.status==="stopping"){await stop("end_phrase");return true;}
  return false;
}

async function requestFarewell(callId=null){
  if(!farewellPending){
    farewellPending=true;farewellCallId=typeof callId==="string"?callId:null;
    if(inputTrack)inputTrack.enabled=false;
    setUiState("stopping","Saying goodbye before returning to wake listening.");showEndControl(false);
    if(responseActive&&!farewellCallId&&dc?.readyState==="open"){
      if(assistantSpeaking)dc.send(JSON.stringify({type:"output_audio_buffer.clear"}));
      dc.send(JSON.stringify({type:"response.cancel"}));
    }
  }else if(!farewellCallId&&typeof callId==="string")farewellCallId=callId;
  if(!responseActive&&!turnResponsePending&&!farewellStarted)await startFarewell();
}

async function startFarewell(){
  if(farewellStarted||!farewellPending||dc?.readyState!=="open")return;
  farewellStarted=true;
  await hostEvent("farewell_started");
  if(farewellCallId)dc.send(JSON.stringify({type:"conversation.item.create",item:{type:"function_call_output",call_id:farewellCallId,output:JSON.stringify({status:"ending"})}}));
  dc.send(JSON.stringify({
    type:"response.create",
    response:{
      output_modalities:["audio"],
      instructions:"Say exactly one brief, warm farewell in the language of the user's current utterance. For Mandarin Chinese say only 再见. For English say only Goodbye. Do not add anything else.",
      tools:[],
      tool_choice:"none",
      metadata:{purpose:"farewell"},
    },
  }));
}

async function finishIfStopping(result,reason){if(result?.status==="stopping")await stop(reason);}

function startRealtimeAcknowledgement(){
  if(!realtimeAcknowledgement||acknowledgementStarted||dc?.readyState!=="open")return;
  if(acknowledgementCaptureLabel&&!acknowledgementCapture)return;
  acknowledgementStarted=true;
  dc.send(JSON.stringify({
    type:"response.create",
    response:{
      output_modalities:["audio"],
      instructions:"请只用自然、温暖的普通话说：嗯，我在，请说。不要添加其他内容。",
      tools:[],
      tool_choice:"none",
      metadata:{purpose:"acknowledgement"},
    },
  }));
}

async function reportConfiguredSession(){
  if(sessionCreatedAt===null||dataChannelOpenedAt===null||!transportReported||configurationReportStarted)return;
  configurationReportStarted=true;
  const readyAt=Math.max(sessionCreatedAt,handoffTiming.negotiationCompleted);
  await hostEvent("session_created");
  await hostEvent("handoff_timing",handoffTimingSummary(readyAt));
  await hostEvent("session_configured");
  sessionCreatedAt=null;dataChannelOpenedAt=null;
  setUiState("connecting","Connected securely. Waiting for the ready acknowledgement.");
  startRealtimeAcknowledgement();
}

async function handleServerEvent(event){
  const tracked=["session.created","input_audio_buffer.speech_started","input_audio_buffer.speech_stopped","response.created","response.done","response.output_audio_transcript.done","output_audio_buffer.started","output_audio_buffer.stopped","response.function_call_arguments.done","conversation.item.input_audio_transcription.completed","conversation.item.input_audio_transcription.failed","error"];
  if(!tracked.includes(event.type))return;
  log(event.type,{status:event.response?.status});
  if(event.type==="session.created"){sessionCreatedAt=performance.now();await reportConfiguredSession();}
  if(event.type==="input_audio_buffer.speech_started"){setUiState("listening","I can hear you.");await hostEvent("speech_started");}
  if(event.type==="input_audio_buffer.speech_stopped"){turnResponsePending=true;setUiState("thinking");await hostEvent("speech_stopped");}
  if(event.type==="response.created"){
    responseActive=true;turnResponsePending=false;flushInputLevels();
    if(event.response?.metadata?.purpose==="acknowledgement"){
      acknowledgementResponseActive=true;setUiState("connecting","Playing the acknowledgement.");
      await hostEvent("realtime_ack_response_created");
    }else if(event.response?.metadata?.purpose==="farewell"){
      farewellResponseActive=true;setUiState("stopping","Saying goodbye before returning to wake listening.");
      await hostEvent("farewell_response_created");
    }else{
      setUiState(farewellPending?"stopping":"thinking",farewellPending?"Saying goodbye before returning to wake listening.":undefined);
      await hostEvent("response_created");
      if(farewellPending&&dc?.readyState==="open")dc.send(JSON.stringify({type:"response.cancel"}));
    }
  }
  if(event.type==="response.done"){
    responseActive=false;turnResponsePending=false;flushInputLevels();
    if(event.response?.metadata?.purpose==="acknowledgement"){
      acknowledgementTranscript=acknowledgementTranscript||responseTranscript(event.response);
      await finishIfStopping(await hostEvent("realtime_ack_response_done",{reason:String(event.response?.status||"unknown")}),"realtime_acknowledgement_failed");
    }else if(event.response?.metadata?.purpose==="farewell"){
      await finishIfStopping(await hostEvent("farewell_response_done",{reason:String(event.response?.status||"unknown")}),"farewell_complete");
    }else{
      await hostEvent("response_done",{reason:String(event.response?.status||"unknown")});
      for(const item of event.response?.output||[])if(item.type==="function_call"&&await forwardToolCall(item))break;
    }
    if(farewellPending&&!farewellStarted)await startFarewell();
  }
  if(event.type==="response.output_audio_transcript.done"&&acknowledgementResponseActive&&typeof event.transcript==="string")acknowledgementTranscript=event.transcript;
  if(event.type==="output_audio_buffer.started"){
    flushInputLevels();assistantSpeaking=true;
    if(acknowledgementResponseActive){setUiState("connecting","Playing the acknowledgement.");await hostEvent("realtime_ack_playback_started");}
    else if(farewellResponseActive){setUiState("stopping","Saying goodbye before returning to wake listening.");await hostEvent("farewell_playback_started");}
    else{setUiState("speaking");await hostEvent("playback_started");}
  }
  if(event.type==="output_audio_buffer.stopped"){
    flushInputLevels();assistantSpeaking=false;
    if(acknowledgementResponseActive){
      acknowledgementResponseActive=false;
      if(acknowledgementCaptureLabel){
        try{await uploadAcknowledgementCapture();}
        catch{await hostEvent("error",{reason:"acknowledgement_capture_failed"}).catch(()=>{});await stop("acknowledgement_capture_failed","error");return;}
      }
      await finishIfStopping(await hostEvent("realtime_ack_playback_stopped"),"realtime_acknowledgement_failed");
    }else if(farewellResponseActive){
      farewellResponseActive=false;
      await finishIfStopping(await hostEvent("farewell_playback_stopped"),"farewell_complete");
    }else{setUiState(farewellPending?"stopping":"listening");await hostEvent("playback_stopped");}
  }
  if(event.type==="response.function_call_arguments.done")await forwardToolCall(event);
  if(event.type==="conversation.item.input_audio_transcription.completed"){
    const transcript=typeof event.transcript==="string"&&event.transcript.length<=200?event.transcript:null;
    const result=await hostEvent("transcription",{item_id:event.item_id,transcript});
    if(result.status==="farewell")await requestFarewell();
    if(result.status==="stopping")await stop("end_phrase");
  }
  if(event.type==="conversation.item.input_audio_transcription.failed")await hostEvent("transcription_failed",{item_id:event.item_id});
  if(event.type==="error"){await hostEvent("error",{reason:"realtime_error"}).catch(()=>{});await stop("realtime_error","error");}
}

async function start(command){
  if(!armed||pc)throw new Error("host is not ready for start");
  handoffTiming={commandReceived:performance.now()};sessionCreatedAt=null;dataChannelOpenedAt=null;transportReported=false;configurationReportStarted=false;
  responseActive=false;turnResponsePending=false;farewellPending=false;farewellStarted=false;farewellCallId=null;farewellResponseActive=false;
  realtimeAcknowledgement=command.acknowledgement_mode==="realtime";acknowledgementStarted=false;acknowledgementResponseActive=false;
  acknowledgementCaptureLabel=typeof command.acknowledgement_capture_label==="string"?command.acknowledgement_capture_label:null;acknowledgementCapture=null;acknowledgementTranscript=null;remoteStream=null;
  sessionId=command.session_id;setUiState("connecting");showEndControl(true);
  if(command.acknowledgement_mode==="cached")startCachedAcknowledgement(command).catch(async()=>{if(sessionId===command.session_id){await hostEvent("error",{reason:"cached_acknowledgement_failed"}).catch(()=>{});await stop("cached_acknowledgement_failed","error");}});
  await hostEvent("microphone_requested");
  if(sessionId!==command.session_id)return;
  handoffTiming.tokenStarted=handoffTiming.tokenAcquired=handoffTiming.commandReceived;
  handoffTiming.microphoneStarted=handoffTiming.commandReceived;
  const retainedTrack=warmStream?.getAudioTracks()[0];
  if(KEEP_WARM_MICROPHONE&&retainedTrack?.readyState==="live")stream=warmStream;
  else{
    if(warmStream){warmStream.getTracks().forEach(track=>track.stop());warmStream=null;}
    stream=await navigator.mediaDevices.getUserMedia({audio:AUDIO_CONSTRAINTS});
    if(KEEP_WARM_MICROPHONE)warmStream=stream;
  }
  handoffTiming.microphoneAcquired=performance.now();
  const track=stream.getAudioTracks()[0],echoPreference=await preferStrongestEchoCancellation(track),settings=track.getSettings();renderSettings(settings);
  track.enabled=false;inputTrack=track;
  await hostEvent("microphone_acquired",{echoCancellation:settings.echoCancellation,echoCancellationRequested:echoPreference.requested,echoCancellationAllSupported:echoPreference.allSupported,noiseSuppression:settings.noiseSuppression,autoGainControl:settings.autoGainControl,inputNoiseReduction:sessionConfig.input_noise_reduction,sampleRate:settings.sampleRate,channelCount:settings.channelCount,outputVolume:configuredOutputVolume()});
  handoffTiming.microphoneReported=performance.now();
  if(command.input_level_diagnostics===true)startInputLevels(stream,handoffTiming);
  else skipInputLevels(handoffTiming);
  pc=new RTCPeerConnection();
  pc.ontrack=event=>{remoteStream=event.streams[0];if(acknowledgementCaptureLabel&&!acknowledgementCapture){try{acknowledgementCapture=createAcknowledgementCapture(remoteStream);}catch{hostEvent("error",{reason:"acknowledgement_capture_failed"}).catch(()=>{});stop("acknowledgement_capture_failed","error").catch(()=>{});return;}}attachRemoteAudio().catch(error=>log("remote_audio_play_failed",{message:String(error.message).slice(0,120)}));};
  pc.onconnectionstatechange=()=>{if(pc&&["failed","closed"].includes(pc.connectionState)&&sessionId)stop(`peer_${pc.connectionState}`).catch(()=>{});};
  pc.addTrack(track,stream);
  dc=pc.createDataChannel("oai-events");
  dc.onopen=()=>{dataChannelOpenedAt=performance.now();reportConfiguredSession().catch(()=>{});};
  dc.onmessage=event=>{let data;try{data=JSON.parse(event.data)}catch{return}handleServerEvent(data).catch(()=>{});};
  dc.onclose=()=>{if(sessionId)stop("data_channel_closed").catch(()=>{});};
  handoffTiming.peerConnectionReady=performance.now();
  const offer=await pc.createOffer();handoffTiming.offerCreated=performance.now();
  await pc.setLocalDescription(offer);handoffTiming.negotiationStarted=performance.now();
  const answer=await fetch("/session",{method:"POST",body:offer.sdp,headers:{"Content-Type":"application/sdp"}});
  if(!answer.ok)throw await negotiationFailure(answer);
  await pc.setRemoteDescription({type:"answer",sdp:await answer.text()});
  if(acknowledgementCaptureLabel&&!acknowledgementCapture){
    const remoteTrack=pc.getReceivers().map(receiver=>receiver.track).find(track=>track?.kind==="audio");
    if(!remoteTrack)throw new Error("Remote ACK capture track is unavailable");
    remoteStream=remoteStream||new MediaStream([remoteTrack]);acknowledgementCapture=createAcknowledgementCapture(remoteStream);
  }
  handoffTiming.negotiationCompleted=performance.now();
  await hostEvent("transport_connected");
  transportReported=true;await reportConfiguredSession();
  setUiState("connecting","Secure transport connected. Finishing voice setup.");log("transport_connected");
}

async function enableInput(command){
  if(command.session_id!==sessionId||!inputTrack||inputTrack.enabled||dc?.readyState!=="open")throw new Error("input enablement requires the configured active session");
  inputTrack.enabled=true;
  await hostEvent("connected");
  setUiState("listening");log("input_ready");
}

async function stop(reason="command",finalState="wake-ready"){
  const endingSession=sessionId;if(!endingSession)return;stopInputLevels();sessionId=null;
  if(acknowledgementCapture){acknowledgementCapture.abort();acknowledgementCapture=null;}
  resetCachedAcknowledgementPlayback();
  setUiState("stopping");showEndControl(false);
  const channel=dc;dc=null;if(channel){channel.onclose=null;try{channel.close()}catch{}}
  const peer=pc;pc=null;if(peer){peer.onconnectionstatechange=null;try{peer.close()}catch{}}
  if(stream){
    if(KEEP_WARM_MICROPHONE&&stream===warmStream&&stream.getAudioTracks()[0]?.readyState==="live")stream.getAudioTracks().forEach(track=>{track.enabled=false;});
    else stream.getTracks().forEach(track=>track.stop());
    stream=null;
  }inputTrack=null;
  const audio=$("remoteAudio");
  if(KEEP_WARM_MICROPHONE&&warmStream?.getAudioTracks()[0]?.readyState==="live"){audio.srcObject=warmStream;audio.volume=0;const playAttempt=audio.play();if(playAttempt)playAttempt.catch(()=>{});}
  else{audio.pause();audio.srcObject=null;}
  handoffTiming=null;sessionCreatedAt=null;dataChannelOpenedAt=null;transportReported=false;configurationReportStarted=false;
  responseActive=false;turnResponsePending=false;farewellPending=false;farewellStarted=false;farewellCallId=null;farewellResponseActive=false;assistantSpeaking=false;
  realtimeAcknowledgement=false;acknowledgementStarted=false;acknowledgementResponseActive=false;acknowledgementCaptureLabel=null;acknowledgementTranscript=null;remoteStream=null;
  log("stopped",{reason});
  sessionId=endingSession;await hostEvent("stopped",{reason}).catch(()=>{});sessionId=null;
  setUiState(finalState);
}

async function openAppSettings(){
  armed=false;
  try{if(sessionId)await stop("open_settings");}catch{}
  stopInputLevels();
  releasePageMedia();
  window.location.assign("hey-jarvis://settings/open");
}

function failClosedAvailability(){
  armed=false;
  stopInputLevels();
  releasePageMedia();
  showEndControl(false);
  $("arm").disabled=true;
  $("arm").hidden=true;
  setUiState("resume-required");
}

async function refreshAvailability(){
  try{
    const response=await fetch("/api/availability",{cache:"no-store"});
    const data=await response.json();
    if(!response.ok)throw new Error(data.error||"availability_unavailable");
    if(data.availability==="resume_required"){failClosedAvailability();return;}
    if(data.availability==="ready"&&!armed&&!sessionId)setUiState("ready");
    if(data.availability==="wake_listening"&&armed&&!sessionId)setUiState("wake-ready");
  }catch{failClosedAvailability();}
}

async function sendFixtureAudio(command){
  if(command.session_id!==sessionId||dc?.readyState!=="open")throw new Error("fixture audio requires an open session");
  const audio=command.audio;if(typeof audio!=="string"||!audio.length)throw new Error("fixture audio payload is missing");
  dc.send(JSON.stringify({type:"conversation.item.create",item:{type:"message",role:"user",content:[{type:"input_audio",audio}]}}));
  await hostEvent("fixture_submitted");
  dc.send(JSON.stringify({type:"response.create"}));
  log("fixture_audio_sent",{name:String(command.fixture_name||"unknown")});
}

async function poll(){while(armed){try{const data=await fetch(`/api/command?after=${lastCommand}&host_id=${hostId}`,{cache:"no-store"}).then(response=>response.json());const command=data.command;if(command){lastCommand=command.command_id;if(command.type==="start")await start(command);if(command.type==="enable_input")await enableInput(command);if(command.type==="long_answer"&&command.session_id===sessionId)longAnswer();if(command.type==="fixture_audio")await sendFixtureAudio(command);if(command.type==="tool_result"&&command.session_id===sessionId&&dc?.readyState==="open"){dc.send(JSON.stringify({type:"conversation.item.create",item:{type:"function_call_output",call_id:command.call_id,output:command.output}}));dc.send(JSON.stringify({type:"response.create"}));}if(command.type==="stop"&&command.session_id===sessionId)await stop("python_stop");}}catch(error){log("command_error",{message:String(error.message).slice(0,120)});if(sessionId){const diagnostic=error&&typeof error==="object"&&error.safeDiagnostic?error.safeDiagnostic:{reason:"host_command_failure"};await hostEvent("error",diagnostic).catch(()=>{});await stop("error","error");}}await new Promise(resolve=>setTimeout(resolve,250));}}
function longAnswer(){if(!dc||dc.readyState!=="open")return;dc.send(JSON.stringify({type:"conversation.item.create",item:{type:"message",role:"user",content:[{type:"input_text",text:"Count slowly from one to one hundred, saying every number clearly. Do not abbreviate or skip any number."}]}}));dc.send(JSON.stringify({type:"response.create"}));}

$("arm").addEventListener("click",()=>{$("arm").disabled=true;arm();});$("stop").addEventListener("click",()=>{setUiState("stopping");$("stop").disabled=true;post("/api/stop").catch(error=>setUiState("error",`Could not end the conversation: ${error.message}`));});$("app-settings").addEventListener("click",openAppSettings);
function releasePageMedia(){
  if(acknowledgementCapture){acknowledgementCapture.abort();acknowledgementCapture=null;}
  resetCachedAcknowledgementPlayback();
  if(cachedAcknowledgementUrl){URL.revokeObjectURL(cachedAcknowledgementUrl);cachedAcknowledgementUrl=null;}
  acknowledgementCaptureLabel=null;acknowledgementTranscript=null;remoteStream=null;
  const activeStream=stream;stream=null;
  if(activeStream)activeStream.getTracks().forEach(track=>track.stop());
  if(warmStream&&warmStream!==activeStream)warmStream.getTracks().forEach(track=>track.stop());
  warmStream=null;
  inputTrack=null;
  const audio=$("remoteAudio");audio.pause();audio.srcObject=null;
  if(dc){try{dc.close()}catch{}dc=null;}
  if(pc){try{pc.close()}catch{}pc=null;}
}
window.addEventListener("beforeunload",releasePageMedia);
window.addEventListener("pagehide",releasePageMedia);
document.addEventListener("freeze",releasePageMedia);
refreshAvailability();
setInterval(refreshAvailability,1000);
