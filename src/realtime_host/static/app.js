"use strict";

const AUDIO_CONSTRAINTS={echoCancellation:true,noiseSuppression:true,autoGainControl:true,channelCount:1};
let armed=false,lastCommand=0,pc=null,dc=null,stream=null,sessionId=null,sessionConfig=null,events=[];
const hostId=crypto.randomUUID().replaceAll("-","");
const $=id=>document.getElementById(id);

function log(type,detail={}){events.push({at_ms:Math.round(performance.now()),type,...detail});events=events.slice(-100);$("events").textContent=events.map(JSON.stringify).join("\n");}
async function post(path,payload={}){const response=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw new Error(data.message||data.error);return data;}
async function hostEvent(type,detail={}){return post("/api/event",{type,session_id:sessionId,host_id:hostId,...detail});}
function renderSettings(settings){for(const row of $("settings").querySelectorAll("div")){const key=row.querySelector("dt").textContent;row.querySelector("dd").textContent=String(settings[key]??"not reported");}}

async function arm(){
  try{
    const warm=await navigator.mediaDevices.getUserMedia({audio:AUDIO_CONSTRAINTS});
    renderSettings(warm.getAudioTracks()[0]?.getSettings()||{});
    warm.getTracks().forEach(track=>track.stop());
    const playAttempt=$("remoteAudio").play();if(playAttempt)playAttempt.catch(()=>{});
    sessionId=null;await hostEvent("armed");armed=true;$("arm").disabled=true;
    $("status").textContent="Armed · waiting for Python wake";log("armed");poll();
  }catch(error){$("status").textContent=`Arm failed: ${error.message}`;}
}

function sendSessionUpdate(){
  const turnDetection=sessionConfig.server_vad?{type:"server_vad",threshold:0.5,prefix_padding_ms:300,silence_duration_ms:500,create_response:true,interrupt_response:true}:null;
  const input={turn_detection:turnDetection};
  if(sessionConfig.input_transcription)input.transcription={model:sessionConfig.transcription_model};
  dc.send(JSON.stringify({type:"session.update",session:{type:"realtime",model:sessionConfig.model,output_modalities:["audio"],audio:{input,output:{voice:sessionConfig.voice}}}}));
}

async function handleServerEvent(event){
  const tracked=["session.created","session.updated","input_audio_buffer.speech_started","input_audio_buffer.speech_stopped","response.created","response.done","conversation.item.input_audio_transcription.completed","conversation.item.input_audio_transcription.failed","error"];
  if(!tracked.includes(event.type))return;
  log(event.type,{status:event.response?.status});
  if(event.type==="session.created"){await hostEvent("session_created");sendSessionUpdate();}
  if(event.type==="session.updated"){await hostEvent("connected");$("status").textContent="Live · follow-up speech stays in this session";}
  if(event.type==="input_audio_buffer.speech_started")await hostEvent("speech_started");
  if(event.type==="input_audio_buffer.speech_stopped")await hostEvent("speech_stopped");
  if(event.type==="response.created")await hostEvent("response_created");
  if(event.type==="response.done")await hostEvent("response_done",{reason:String(event.response?.status||"unknown")});
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
  sessionId=command.session_id;$("status").textContent="Python released wake microphone · connecting";
  await hostEvent("microphone_requested");
  const token=await fetch("/token",{method:"POST"}).then(async response=>{const data=await response.json();if(!response.ok)throw new Error(data.message||data.error);return data;});
  sessionConfig=token.session;
  stream=await navigator.mediaDevices.getUserMedia({audio:AUDIO_CONSTRAINTS});
  const track=stream.getAudioTracks()[0],settings=track.getSettings();renderSettings(settings);
  await hostEvent("microphone_acquired",{echoCancellation:settings.echoCancellation,noiseSuppression:settings.noiseSuppression,autoGainControl:settings.autoGainControl,sampleRate:settings.sampleRate,channelCount:settings.channelCount});
  pc=new RTCPeerConnection();
  pc.ontrack=event=>{$("remoteAudio").srcObject=event.streams[0];log("remote_audio_track")};
  pc.onconnectionstatechange=()=>{if(pc&&["failed","closed"].includes(pc.connectionState)&&sessionId)stop(`peer_${pc.connectionState}`).catch(()=>{});};
  pc.addTrack(track,stream);
  dc=pc.createDataChannel("oai-events");
  dc.onmessage=event=>{let data;try{data=JSON.parse(event.data)}catch{return}handleServerEvent(data).catch(()=>{});};
  dc.onclose=()=>{if(sessionId)stop("data_channel_closed").catch(()=>{});};
  const offer=await pc.createOffer();await pc.setLocalDescription(offer);
  const answer=await fetch("https://api.openai.com/v1/realtime/calls",{method:"POST",body:offer.sdp,headers:{Authorization:`Bearer ${token.value}`,"Content-Type":"application/sdp"}});
  if(!answer.ok)throw new Error(`WebRTC negotiation failed (${answer.status})`);
  await pc.setRemoteDescription({type:"answer",sdp:await answer.text()});
  await hostEvent("transport_connected");
  $("status").textContent="Connecting · waiting for session.created";$("long").disabled=false;$("stop").disabled=false;log("transport_connected");
}

async function stop(reason="command"){
  const endingSession=sessionId;if(!endingSession)return;sessionId=null;
  const channel=dc;dc=null;if(channel){channel.onclose=null;try{channel.close()}catch{}}
  const peer=pc;pc=null;if(peer){peer.onconnectionstatechange=null;try{peer.close()}catch{}}
  if(stream){stream.getTracks().forEach(track=>track.stop());stream=null;}
  const audio=$("remoteAudio");audio.pause();audio.srcObject=null;sessionConfig=null;
  $("long").disabled=true;$("stop").disabled=true;log("stopped",{reason});
  sessionId=endingSession;await hostEvent("stopped",{reason}).catch(()=>{});sessionId=null;
  $("status").textContent="Armed · Python wake microphone restored";
}

async function poll(){while(armed){try{const data=await fetch(`/api/command?after=${lastCommand}&host_id=${hostId}`,{cache:"no-store"}).then(response=>response.json());const command=data.command;if(command){lastCommand=command.command_id;if(command.type==="start")await start(command);if(command.type==="long_answer"&&command.session_id===sessionId)longAnswer();if(command.type==="stop"&&command.session_id===sessionId)await stop("python_stop");}}catch(error){log("command_error",{message:String(error.message).slice(0,120)});if(sessionId){await hostEvent("error",{reason:"host_command_failure"}).catch(()=>{});await stop("error");}}await new Promise(resolve=>setTimeout(resolve,250));}}
function longAnswer(){if(!dc||dc.readyState!=="open")return;dc.send(JSON.stringify({type:"conversation.item.create",item:{type:"message",role:"user",content:[{type:"input_text",text:"Count slowly from one to one hundred, saying every number clearly. Do not abbreviate or skip any number."}]}}));dc.send(JSON.stringify({type:"response.create"}));}

$("arm").addEventListener("click",arm);$("long").addEventListener("click",longAnswer);$("stop").addEventListener("click",()=>post("/api/stop"));window.addEventListener("beforeunload",()=>{if(stream)stream.getTracks().forEach(track=>track.stop());});
