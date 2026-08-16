export function assistantModeFragment({ recovery = false, smartSpeakerMode = false } = {}) {
  if (recovery) return "smart-speaker-resume";
  return smartSpeakerMode === true ? "smart-speaker-mode" : "";
}
