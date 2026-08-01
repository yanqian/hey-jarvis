"use strict";

const AUDIO_CONSTRAINTS={echoCancellation:{exact:true},noiseSuppression:true,autoGainControl:true,channelCount:1};
const REMOTE_AUDIO_VOLUME=0.1;
const INPUT_LEVEL_SAMPLE_INTERVAL_MS=100,INPUT_LEVEL_WINDOW_SAMPLES=5;
let armed=false,lastCommand=0,pc=null,dc=null,stream=null,inputTrack=null,sessionId=null,sessionConfig=null,events=[],handoffTiming=null,sessionCreatedAt=null,dataChannelOpenedAt=null,transportReported=false,configurationReportStarted=false;
let levelContext=null,levelAnalyser=null,levelSource=null,levelTimer=null,levelSamples=[],assistantSpeaking=false;
const hostId=crypto.randomUUID().replaceAll("-","");
const $=id=>document.getElementById(id);

function log(type,detail={}){events.push({at_ms:Math.round(performance.now()),type,...detail});events=events.slice(-100);$("events").textContent=events.map(JSON.stringify).join("\n");}
async function post(path,payload={}){const response=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data.message||data.error);return data;}
async function hostEvent(type,detail={}){return post("/api/event",{type,session_id:sessionId,host_id:hostId,...detail});}
function renderSettings(settings){for(const row of $("settings").querySelectorAll("div")){const key=row.querySelector("dt").textContent;row.querySelector("dd").textContent=String(settings[key]??"not reported");}}
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
    renderSettings(warm.getAudioTracks()[0]?.getSettings()||{});
    warm.getTracks().forEach(track=>track.stop());
    $("remoteAudio").volume=Number.isFinite(sessionConfig.output_volume)?sessionConfig.output_volume:REMOTE_AUDIO_VOLUME;
    const playAttempt=$("remoteAudio").play();if(playAttempt)playAttempt.catch(()=>{});
    sessionId=null;await hostEvent("armed");armed=true;$("arm").disabled=true;
    $("status").textContent="Armed · waiting for Python wake";log("armed");poll();
  }catch(error){$("status").textContent=`Arm failed: ${error.message}`;}
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
  if(result.status==="stopping"){await stop("end_phrase");return true;}
  return false;
}

async function reportConfiguredSession(){
  if(sessionCreatedAt===null||dataChannelOpenedAt===null||!transportReported||configurationReportStarted)return;
  configurationReportStarted=true;
  const readyAt=Math.max(sessionCreatedAt,handoffTiming.negotiationCompleted);
  await hostEvent("session_created");
  await hostEvent("handoff_timing",handoffTimingSummary(readyAt));
  await hostEvent("session_configured");
  sessionCreatedAt=null;dataChannelOpenedAt=null;
  $("status").textContent="Configured · waiting for audible ready acknowledgement";
}

async function handleServerEvent(event){
  const tracked=["session.created","input_audio_buffer.speech_started","input_audio_buffer.speech_stopped","response.created","response.done","output_audio_buffer.started","output_audio_buffer.stopped","response.function_call_arguments.done","conversation.item.input_audio_transcription.completed","conversation.item.input_audio_transcription.failed","error"];
  if(!tracked.includes(event.type))return;
  log(event.type,{status:event.response?.status});
  if(event.type==="session.created"){sessionCreatedAt=performance.now();await reportConfiguredSession();}
  if(event.type==="input_audio_buffer.speech_started")await hostEvent("speech_started");
  if(event.type==="input_audio_buffer.speech_stopped")await hostEvent("speech_stopped");
  if(event.type==="response.created"){flushInputLevels();await hostEvent("response_created");}
  if(event.type==="response.done"){
    flushInputLevels();
    await hostEvent("response_done",{reason:String(event.response?.status||"unknown")});
    for(const item of event.response?.output||[])if(item.type==="function_call"&&await forwardToolCall(item))return;
  }
  if(event.type==="output_audio_buffer.started"){flushInputLevels();assistantSpeaking=true;await hostEvent("playback_started");}
  if(event.type==="output_audio_buffer.stopped"){flushInputLevels();assistantSpeaking=false;await hostEvent("playback_stopped");}
  if(event.type==="response.function_call_arguments.done")await forwardToolCall(event);
  if(event.type==="conversation.item.input_audio_transcription.completed"){
    const transcript=typeof event.transcript==="string"&&event.transcript.length<=200?event.transcript:null;
    const result=await hostEvent("transcription",{item_id:event.item_id,transcript});
    if(result.status==="stopping")await stop("end_phrase");
  }
  if(event.type==="conversation.item.input_audio_transcription.failed")await hostEvent("transcription_failed",{item_id:event.item_id});
  if(event.type==="error"){await hostEvent("error",{reason:"realtime_error"}).catch(()=>{});await stop("realtime_error");}
}

async function start(command){
  if(!armed||pc)throw new Error("host is not ready for start");
  handoffTiming={commandReceived:performance.now()};sessionCreatedAt=null;dataChannelOpenedAt=null;transportReported=false;configurationReportStarted=false;
  sessionId=command.session_id;$("status").textContent="Python released wake microphone · connecting";
  await hostEvent("microphone_requested");
  handoffTiming.tokenStarted=handoffTiming.tokenAcquired=handoffTiming.commandReceived;
  handoffTiming.microphoneStarted=handoffTiming.commandReceived;
  $("remoteAudio").volume=Number.isFinite(sessionConfig.output_volume)?sessionConfig.output_volume:REMOTE_AUDIO_VOLUME;
  stream=await navigator.mediaDevices.getUserMedia({audio:AUDIO_CONSTRAINTS});
  handoffTiming.microphoneAcquired=performance.now();
  const track=stream.getAudioTracks()[0],echoPreference=await preferStrongestEchoCancellation(track),settings=track.getSettings();renderSettings(settings);
  track.enabled=false;inputTrack=track;
  await hostEvent("microphone_acquired",{echoCancellation:settings.echoCancellation,echoCancellationRequested:echoPreference.requested,echoCancellationAllSupported:echoPreference.allSupported,noiseSuppression:settings.noiseSuppression,autoGainControl:settings.autoGainControl,inputNoiseReduction:sessionConfig.input_noise_reduction,sampleRate:settings.sampleRate,channelCount:settings.channelCount,outputVolume:$("remoteAudio").volume});
  handoffTiming.microphoneReported=performance.now();
  if(command.input_level_diagnostics===true)startInputLevels(stream,handoffTiming);
  else skipInputLevels(handoffTiming);
  pc=new RTCPeerConnection();
  pc.ontrack=event=>{$("remoteAudio").srcObject=event.streams[0];log("remote_audio_track")};
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
  handoffTiming.negotiationCompleted=performance.now();
  await hostEvent("transport_connected");
  transportReported=true;await reportConfiguredSession();
  $("status").textContent="Connecting · waiting for session.created";$("long").disabled=false;$("stop").disabled=false;log("transport_connected");
}

async function enableInput(command){
  if(command.session_id!==sessionId||!inputTrack||inputTrack.enabled||dc?.readyState!=="open")throw new Error("input enablement requires the configured active session");
  inputTrack.enabled=true;
  await hostEvent("connected");
  $("status").textContent="Live · input ready; follow-up speech stays in this session";log("input_ready");
}

async function stop(reason="command"){
  const endingSession=sessionId;if(!endingSession)return;stopInputLevels();sessionId=null;
  const channel=dc;dc=null;if(channel){channel.onclose=null;try{channel.close()}catch{}}
  const peer=pc;pc=null;if(peer){peer.onconnectionstatechange=null;try{peer.close()}catch{}}
  if(stream){stream.getTracks().forEach(track=>track.stop());stream=null;}inputTrack=null;
  const audio=$("remoteAudio");audio.pause();audio.srcObject=null;handoffTiming=null;sessionCreatedAt=null;dataChannelOpenedAt=null;transportReported=false;configurationReportStarted=false;
  $("long").disabled=true;$("stop").disabled=true;log("stopped",{reason});
  sessionId=endingSession;await hostEvent("stopped",{reason}).catch(()=>{});sessionId=null;
  $("status").textContent="Armed · Python wake microphone restored";
}

async function openAppSettings(){
  armed=false;
  try{if(sessionId)await stop("open_settings");}catch{}
  stopInputLevels();
  if(stream){stream.getTracks().forEach(track=>track.stop());stream=null;}inputTrack=null;
  const audio=$("remoteAudio");audio.pause();audio.srcObject=null;
  if(window.history.length>1)window.history.back();
  else $("status").textContent="Open Settings from the Hey Jarvis tray menu.";
}

async function sendFixtureAudio(command){
  if(command.session_id!==sessionId||dc?.readyState!=="open")throw new Error("fixture audio requires an open session");
  const audio=command.audio;if(typeof audio!=="string"||!audio.length)throw new Error("fixture audio payload is missing");
  dc.send(JSON.stringify({type:"conversation.item.create",item:{type:"message",role:"user",content:[{type:"input_audio",audio}]}}));
  await hostEvent("fixture_submitted");
  dc.send(JSON.stringify({type:"response.create"}));
  log("fixture_audio_sent",{name:String(command.fixture_name||"unknown")});
}

async function poll(){while(armed){try{const data=await fetch(`/api/command?after=${lastCommand}&host_id=${hostId}`,{cache:"no-store"}).then(response=>response.json());const command=data.command;if(command){lastCommand=command.command_id;if(command.type==="start")await start(command);if(command.type==="enable_input")await enableInput(command);if(command.type==="long_answer"&&command.session_id===sessionId)longAnswer();if(command.type==="fixture_audio")await sendFixtureAudio(command);if(command.type==="tool_result"&&command.session_id===sessionId&&dc?.readyState==="open"){dc.send(JSON.stringify({type:"conversation.item.create",item:{type:"function_call_output",call_id:command.call_id,output:command.output}}));dc.send(JSON.stringify({type:"response.create"}));}if(command.type==="stop"&&command.session_id===sessionId)await stop("python_stop");}}catch(error){log("command_error",{message:String(error.message).slice(0,120)});if(sessionId){const diagnostic=error&&typeof error==="object"&&error.safeDiagnostic?error.safeDiagnostic:{reason:"host_command_failure"};await hostEvent("error",diagnostic).catch(()=>{});await stop("error");}}await new Promise(resolve=>setTimeout(resolve,250));}}
function longAnswer(){if(!dc||dc.readyState!=="open")return;dc.send(JSON.stringify({type:"conversation.item.create",item:{type:"message",role:"user",content:[{type:"input_text",text:"Count slowly from one to one hundred, saying every number clearly. Do not abbreviate or skip any number."}]}}));dc.send(JSON.stringify({type:"response.create"}));}

$("arm").addEventListener("click",arm);$("long").addEventListener("click",longAnswer);$("stop").addEventListener("click",()=>post("/api/stop"));$("app-settings").addEventListener("click",openAppSettings);window.addEventListener("beforeunload",()=>{if(stream)stream.getTracks().forEach(track=>track.stop());});
