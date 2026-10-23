/* Reviewed links only. A fan backup is never labelled as an official upload. */
const MUSIC_VIDEO_LABELS=Object.freeze({official_mv:'공식 MV',official_audio:'공식 오디오',official_video:'공식 영상',fan_backup:'팬 백업 · 비공식',karaoke_tj:'TJ 노래방 · 반주',karaoke_ky:'KY 노래방 · 반주',unavailable:'영상 확인 중'});
function musicVideoLabel(s){return MUSIC_VIDEO_LABELS[s.videoSource?.kind]||'YouTube';}
function musicVideoActions(s,source){
 if(s.videoId)return external(catalogVideoUrl(s.videoId),musicVideoLabel(s)+' 보기','button primary');
 return external(source[0].url,'곡 정보 확인','button primary');
}
function musicVideoInfo(s){
 const v=s.videoSource;if(!v)return '';
 const kind=v.kind;
 const help=kind==='fan_backup'?'공식 채널이 아닌 팬 업로드입니다. 원본과 편집·화질이 다를 수 있습니다.':kind.startsWith('karaoke_')?'멤버 가창 영상이 아닌 원곡의 노래방 반주입니다.':kind==='unavailable'?'곡과 참여 멤버가 일치하는 대체 영상을 아직 확인하지 못했습니다.':'';
 const old=s.originalVideoId&&s.originalVideoId!==s.videoId;
 const message=kind.startsWith('karaoke_')?(v.note||help):help;
 const extra=kind!=='unavailable'&&!kind.startsWith('karaoke_')?v.note:'';
 const originalHelp=s.videoId?'원본의 공개 상태를 확인하지 못해 대체 영상을 연결했습니다. 원본이 다시 공개될 수 있으므로 링크는 보존합니다.':'원본의 현재 공개 상태를 확인하지 못했습니다. 직접 확인할 수 있도록 기존 주소는 보존합니다.';
 return `<aside class="music-source-info" data-video-kind="${e(kind)}"><div class="music-source-heading"><strong>${e(musicVideoLabel(s))}</strong>${v.channel?`<span>${e(v.channel)}</span>`:''}</div>${message?`<p>${e(message)}</p>`:''}${extra?`<p>${e(extra)}</p>`:''}${old?`<details class="music-original-source"><summary>기존 원본 링크</summary><p>${e(originalHelp)}</p>${external(catalogVideoUrl(s.originalVideoId),'기존 원본에서 확인')}</details>`:''}</aside>`;
}
