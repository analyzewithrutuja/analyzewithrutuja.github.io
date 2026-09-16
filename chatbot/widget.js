(function(){
  var WORKER_URL = 'https://rutuja-portfolio-chatbot.rutuja-patel.workers.dev';

  var QUICK_REPLIES = [
    { label: 'Grill me 🔥', message: 'Ask yourself 5 tough interview questions (a mix of technical and behavioral) and answer all of them, one after another.' },
    { label: 'Match a job', jdPrompt: true },
    { label: 'Data Analyst fit', message: 'How do you specifically fit a Data Analyst role?' },
    { label: 'Data Scientist fit', message: 'How do you specifically fit a Data Scientist role?' },
    { label: 'Business Analyst fit', message: 'How do you specifically fit a Business Analyst role?' }
  ];
  var HEADER_SUB = 'AI simulation, not the real Rutuja';
  var GREETING = "Hi, I'm an AI simulation of Rutuja, built on her real resume and projects — not the real person. Ask me about my skills, projects, or experience, in my own words, or tap a suggestion below.";
  var NUDGE_TEXT = "Hiring? Ask me anything about Rutuja's work.";
  var NUDGE_DELAY_MS = 20000;
  var NUDGE_SESSION_KEY = 'rp_chat_nudge_shown';

  var bubbleSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var sendSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="16" height="16"><path d="M22 2 11 13" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M22 2 15 22l-4-9-9-4 20-7z" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var micSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="15" height="15"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v4M8 23h8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var stopSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="13" height="13"><rect x="4" y="4" width="16" height="16" rx="2" fill="white"/></svg>';
  var expandSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="15" height="15"><path d="M8 3H5a2 2 0 0 0-2 2v3M16 3h3a2 2 0 0 1 2 2v3M21 16v3a2 2 0 0 1-2 2h-3M8 21H5a2 2 0 0 1-2-2v-3" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var collapseSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="15" height="15"><path d="M4 9h4V5M4 9l6-6M20 9h-4V5M20 9l-6-6M4 15h4v4M4 15l6 6M20 15h-4v4M20 15l-6 6" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var downloadSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="15" height="15"><path d="M12 3v12m0 0-4-4m4 4 4-4M4 21h16" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var speakerOnSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="15" height="15"><path d="M4 9v6h4l5 5V4L8 9H4z" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M17 8a5 5 0 0 1 0 8M20 5a9 9 0 0 1 0 14" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var speakerOffSvg = '<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" width="15" height="15"><path d="M4 9v6h4l5 5V4L8 9H4z" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M17 9l5 5M22 9l-5 5" stroke="rgba(255,255,255,.7)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';

  var state = {
    open: false,
    expanded: false,
    history: [],
    sending: false,
    recording: false,
    mediaRecorder: null,
    audioChunks: [],
    ttsEnabled: false
  };

  function el(tag, attrs, html){
    var node = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (k === 'class') node.className = attrs[k];
        else node.setAttribute(k, attrs[k]);
      }
    }
    if (html !== undefined) node.innerHTML = html;
    return node;
  }

  function escapeHtml(str){
    var div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  function inlineFormat(text){
    text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    text = text.replace(/(https?:\/\/[^\s<]+)/g, function(url){
      var trail = '';
      var m;
      while ((m = url.match(/(&gt;|&lt;|&amp;|[.,;:!?)\]}]+)$/))) {
        trail = m[0] + trail;
        url = url.slice(0, -m[0].length);
      }
      var linkHtml = '<a href="' + url + '" target="_blank" rel="noopener">' + url + '</a>';
      var jumpHtml = '';
      var pm = url.match(/projects\/([a-zA-Z0-9_-]+)\.html/);
      if (pm && document.getElementById('portfolio-' + pm[1])) {
        jumpHtml = ' <button class="rp-jump-btn" data-project="' + pm[1] + '">↓ View on page</button>';
      }
      return linkHtml + trail + jumpHtml;
    });
    return text;
  }

  function renderMessage(text){
    var escaped = escapeHtml(text);
    var lines = escaped.split(/\n/);
    var htmlParts = [];
    var textBuffer = [];

    function flushText(){
      if (textBuffer.length) {
        htmlParts.push(textBuffer.map(inlineFormat).join('<br>'));
        textBuffer = [];
      }
    }

    function splitTableRow(r){
      return r.trim().replace(/^\||\|$/g, '').split('|').map(function(c){ return c.trim(); });
    }

    var i = 0;
    while (i < lines.length) {
      var line = lines[i];
      if (/^\s*\|.*\|\s*$/.test(line)) {
        flushText();
        var rows = [];
        while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) {
          rows.push(lines[i]);
          i++;
        }
        var headerCells = splitTableRow(rows[0]);
        var bodyRows = rows.slice(1);
        if (bodyRows.length && /^[\s:-]+$/.test(bodyRows[0].replace(/\|/g, ''))) {
          bodyRows = bodyRows.slice(1);
        }
        var tableHtml = '<table class="rp-msg-table"><thead><tr>' +
          headerCells.map(function(c){ return '<th>' + inlineFormat(c) + '</th>'; }).join('') +
          '</tr></thead><tbody>' +
          bodyRows.map(function(r){
            return '<tr>' + splitTableRow(r).map(function(c){ return '<td>' + inlineFormat(c) + '</td>'; }).join('') + '</tr>';
          }).join('') +
          '</tbody></table>';
        htmlParts.push('<div class="rp-msg-table-wrap">' + tableHtml + '</div>');
        continue;
      }
      if (/^[-*]\s+/.test(line)) {
        flushText();
        var items = [];
        while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
          items.push('<li>' + inlineFormat(lines[i].replace(/^[-*]\s+/, '')) + '</li>');
          i++;
        }
        htmlParts.push('<ul class="rp-msg-list">' + items.join('') + '</ul>');
        continue;
      }
      if (/^\d+\.\s+/.test(line)) {
        flushText();
        var nitems = [];
        while (i < lines.length && /^\d+\.\s+/.test(lines[i])) {
          nitems.push('<li>' + inlineFormat(lines[i].replace(/^\d+\.\s+/, '')) + '</li>');
          i++;
        }
        htmlParts.push('<ol class="rp-msg-list">' + nitems.join('') + '</ol>');
        continue;
      }
      if (line.trim() !== '') {
        textBuffer.push(line);
      } else {
        flushText();
      }
      i++;
    }
    flushText();
    return htmlParts.join('');
  }

  function buildWidget(){
    var bubble = el('button', { id: 'rp-chat-bubble', 'aria-label': 'Open chat' }, bubbleSvg);

    var nudge = el('div', { id: 'rp-chat-nudge' });
    nudge.appendChild(el('span', {}, NUDGE_TEXT));
    var nudgeClose = el('button', { class: 'rp-nudge-close', 'aria-label': 'Dismiss' }, '×');
    nudge.appendChild(nudgeClose);

    var panel = el('div', { id: 'rp-chat-panel' });

    var header = el('div', { class: 'rp-chat-header' });
    var headerInfo = el('div', { class: 'rp-chat-header-info' });
    headerInfo.appendChild(el('div', { class: 'rp-chat-avatar' }, 'RP'));
    var headerText = el('div');
    headerText.appendChild(el('div', { class: 'rp-chat-header-title' }, "Interview Rutuja"));
    headerText.appendChild(el('div', { class: 'rp-chat-header-sub' }, HEADER_SUB));
    headerInfo.appendChild(headerText);
    header.appendChild(headerInfo);
    var headerActions = el('div', { class: 'rp-chat-header-actions' });
    var ttsBtn = el('button', { id: 'rp-chat-tts', class: 'rp-chat-icon-btn', 'aria-label': 'Turn on voice replies' }, speakerOffSvg);
    var downloadBtn = el('button', { class: 'rp-chat-icon-btn', 'aria-label': 'Download conversation' }, downloadSvg);
    var expandBtn = el('button', { id: 'rp-chat-expand', class: 'rp-chat-icon-btn', 'aria-label': 'Expand chat' }, expandSvg);
    var closeBtn = el('button', { class: 'rp-chat-icon-btn', 'aria-label': 'Close chat' }, '×');
    headerActions.appendChild(ttsBtn);
    headerActions.appendChild(downloadBtn);
    headerActions.appendChild(expandBtn);
    headerActions.appendChild(closeBtn);
    header.appendChild(headerActions);

    var messages = el('div', { class: 'rp-chat-messages', id: 'rp-chat-messages' });

    var quickReplies = el('div', { class: 'rp-chat-quickreplies', id: 'rp-chat-quickreplies' });
    QUICK_REPLIES.forEach(function(qr){
      var btn = el('button', { class: 'rp-quickreply' }, qr.label);
      btn.addEventListener('click', function(){
        if (qr.jdPrompt) {
          addBotMessage("Paste the job description you're evaluating me against, and I'll break down where I match and where there are gaps.");
          var inputEl = document.getElementById('rp-chat-input');
          if (inputEl) inputEl.focus();
        } else {
          sendMessage(qr.message);
        }
      });
      quickReplies.appendChild(btn);
    });

    var inputRow = el('div', { class: 'rp-chat-inputrow' });
    var input = el('input', { id: 'rp-chat-input', type: 'text', placeholder: 'Type a message...', autocomplete: 'off' });
    var micBtn = el('button', { id: 'rp-chat-mic', 'aria-label': 'Record voice message' }, micSvg);
    var sendBtn = el('button', { id: 'rp-chat-send', 'aria-label': 'Send' }, sendSvg);
    inputRow.appendChild(input);
    inputRow.appendChild(micBtn);
    inputRow.appendChild(sendBtn);

    panel.appendChild(header);
    panel.appendChild(messages);
    panel.appendChild(quickReplies);
    panel.appendChild(inputRow);

    document.body.appendChild(bubble);
    document.body.appendChild(nudge);
    document.body.appendChild(panel);

    bubble.addEventListener('click', togglePanel);
    closeBtn.addEventListener('click', togglePanel);
    expandBtn.addEventListener('click', toggleExpand);
    nudgeClose.addEventListener('click', function(e){ e.stopPropagation(); hideNudge(); });
    nudge.addEventListener('click', function(){ hideNudge(); if (!state.open) togglePanel(); });
    sendBtn.addEventListener('click', function(){ sendMessage(input.value); });
    input.addEventListener('keydown', function(e){
      if (e.key === 'Enter' && !state.sending) sendMessage(input.value);
    });
    micBtn.addEventListener('click', toggleRecording);
    input.addEventListener('focus', function(){ setTimeout(syncMobileViewport, 300); });
    input.addEventListener('blur', function(){ setTimeout(syncMobileViewport, 300); });
    downloadBtn.addEventListener('click', downloadTranscript);
    ttsBtn.addEventListener('click', toggleTts);
    messages.addEventListener('click', function(e){
      var btn = e.target.closest && e.target.closest('.rp-jump-btn');
      if (!btn) return;
      var slug = btn.getAttribute('data-project');
      var target = document.getElementById('portfolio-' + slug);
      if (!target) return;
      if (state.open) togglePanel();
      setTimeout(function(){
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        target.classList.add('rp-highlight-card');
        setTimeout(function(){ target.classList.remove('rp-highlight-card'); }, 2000);
      }, 300);
    });

    addBotMessage(GREETING);
  }

  function downloadTranscript(){
    if (!state.history.length) return;
    var lines = state.history.map(function(m){
      return (m.role === 'user' ? 'Visitor: ' : 'Interview Rutuja: ') + m.content;
    });
    var header = 'Conversation with Interview Rutuja\n' + window.location.origin + '\n' + new Date().toLocaleString() + '\n\n';
    var text = header + lines.join('\n\n');
    var blob = new Blob([text], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'rutuja-ai-conversation.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function(){ URL.revokeObjectURL(url); }, 1000);
  }

  function toggleTts(){
    state.ttsEnabled = !state.ttsEnabled;
    var ttsBtn = document.getElementById('rp-chat-tts');
    if (ttsBtn) {
      ttsBtn.innerHTML = state.ttsEnabled ? speakerOnSvg : speakerOffSvg;
      ttsBtn.setAttribute('aria-label', state.ttsEnabled ? 'Turn off voice replies' : 'Turn on voice replies');
      ttsBtn.classList.toggle('rp-tts-active', state.ttsEnabled);
    }
    if (!state.ttsEnabled && window.speechSynthesis) window.speechSynthesis.cancel();
  }

  function speak(text){
    if (!state.ttsEnabled || !window.speechSynthesis) return;
    var plain = text.replace(/<[^>]+>/g, '').replace(/\*\*/g, '').replace(/^[-*]\s+/gm, '').replace(/^\d+\.\s+/gm, '');
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(plain);
    utterance.rate = 1;
    window.speechSynthesis.speak(utterance);
  }

  function togglePanel(){
    state.open = !state.open;
    document.getElementById('rp-chat-panel').classList.toggle('open', state.open);
    hideNudge();
    if (state.open) {
      var input = document.getElementById('rp-chat-input');
      if (input) input.focus();
      syncMobileViewport();
    } else if (state.expanded) {
      toggleExpand();
    } else {
      resetMobileViewport();
    }
  }

  function syncMobileViewport(){
    var panel = document.getElementById('rp-chat-panel');
    if (!panel || !state.open) return;
    if (!window.visualViewport || window.innerWidth > 480) {
      resetMobileViewport();
      return;
    }
    var vv = window.visualViewport;
    panel.style.top = vv.offsetTop + 'px';
    panel.style.height = vv.height + 'px';
    panel.style.bottom = 'auto';
  }

  function resetMobileViewport(){
    var panel = document.getElementById('rp-chat-panel');
    if (!panel) return;
    panel.style.top = '';
    panel.style.height = '';
    panel.style.bottom = '';
  }

  function toggleExpand(){
    state.expanded = !state.expanded;
    var panel = document.getElementById('rp-chat-panel');
    var expandBtn = document.getElementById('rp-chat-expand');
    panel.classList.toggle('expanded', state.expanded);
    expandBtn.innerHTML = state.expanded ? collapseSvg : expandSvg;
    expandBtn.setAttribute('aria-label', state.expanded ? 'Collapse chat' : 'Expand chat');
  }

  function hideNudge(){
    var nudge = document.getElementById('rp-chat-nudge');
    if (nudge) nudge.classList.remove('show');
  }

  function scheduleNudge(){
    try {
      if (sessionStorage.getItem(NUDGE_SESSION_KEY)) return;
    } catch (e) {}
    setTimeout(function(){
      if (state.open) return;
      var nudge = document.getElementById('rp-chat-nudge');
      if (nudge) nudge.classList.add('show');
      try { sessionStorage.setItem(NUDGE_SESSION_KEY, '1'); } catch (e) {}
    }, NUDGE_DELAY_MS);
  }

  function addMessage(text, sender){
    var messages = document.getElementById('rp-chat-messages');
    var msg = el('div', { class: 'rp-msg rp-msg-' + sender }, renderMessage(text));
    messages.appendChild(msg);
    messages.scrollTop = messages.scrollHeight;
  }

  function addBotMessage(text){ addMessage(text, 'bot'); speak(text); }
  function addUserMessage(text){ addMessage(text, 'user'); }

  function showTyping(){
    var messages = document.getElementById('rp-chat-messages');
    var typing = el('div', { class: 'rp-msg-typing', id: 'rp-chat-typing' }, '<span></span><span></span><span></span>');
    messages.appendChild(typing);
    messages.scrollTop = messages.scrollHeight;
  }

  function hideTyping(){
    var typing = document.getElementById('rp-chat-typing');
    if (typing) typing.remove();
  }

  function sendMessage(text){
    text = (text || '').trim();
    if (!text || state.sending) return;

    var input = document.getElementById('rp-chat-input');
    input.value = '';
    addUserMessage(text);
    state.history.push({ role: 'user', content: text });
    state.sending = true;
    showTyping();

    fetch(WORKER_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text, history: state.history.slice(-6) })
    })
    .then(function(res){
      if (!res.ok) throw new Error('Request failed: ' + res.status);
      return res.json();
    })
    .then(function(data){
      hideTyping();
      var reply = data && data.reply ? data.reply : "Sorry, I couldn't get a response. Please try again.";
      addBotMessage(reply);
      state.history.push({ role: 'assistant', content: reply });
    })
    .catch(function(){
      hideTyping();
      addBotMessage("Sorry, something went wrong on my end. Please try again in a moment, or reach Rutuja directly via the contact section.");
    })
    .finally(function(){
      state.sending = false;
    });
  }

  function toggleRecording(){
    if (state.recording) {
      stopRecording();
    } else {
      startRecording();
    }
  }

  function startRecording(){
    if (!navigator.mediaDevices || !window.MediaRecorder) {
      addBotMessage("Voice input isn't supported in this browser. Please type your question instead.");
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(function(stream){
        state.audioChunks = [];
        var recorder;
        try {
          recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        } catch (e) {
          recorder = new MediaRecorder(stream);
        }
        state.mediaRecorder = recorder;
        recorder.addEventListener('dataavailable', function(e){
          if (e.data && e.data.size > 0) state.audioChunks.push(e.data);
        });
        recorder.addEventListener('stop', function(){
          stream.getTracks().forEach(function(t){ t.stop(); });
          var blob = new Blob(state.audioChunks, { type: recorder.mimeType || 'audio/webm' });
          transcribeAudio(blob);
        });
        recorder.start();
        state.recording = true;
        setMicVisual(true);
      })
      .catch(function(){
        addBotMessage("I couldn't access your microphone. Please check your browser permissions, or type your question instead.");
      });
  }

  function stopRecording(){
    if (state.mediaRecorder && state.recording) {
      state.mediaRecorder.stop();
    }
    state.recording = false;
    setMicVisual(false);
  }

  function setMicVisual(isRecording){
    var micBtn = document.getElementById('rp-chat-mic');
    if (!micBtn) return;
    micBtn.innerHTML = isRecording ? stopSvg : micSvg;
    micBtn.classList.toggle('rp-mic-active', isRecording);
  }

  function transcribeAudio(blob){
    var input = document.getElementById('rp-chat-input');
    input.placeholder = 'Transcribing...';
    var form = new FormData();
    form.append('audio', blob, 'voice.webm');

    fetch(WORKER_URL + '/transcribe', { method: 'POST', body: form })
      .then(function(res){
        if (!res.ok) throw new Error('Transcription failed: ' + res.status);
        return res.json();
      })
      .then(function(data){
        input.placeholder = 'Type a message...';
        var text = data && data.text ? data.text.trim() : '';
        if (text) {
          sendMessage(text);
        } else {
          addBotMessage("I couldn't make out any speech there. Please try again or type your question.");
        }
      })
      .catch(function(){
        input.placeholder = 'Type a message...';
        addBotMessage("Sorry, voice transcription failed. Please try again or type your question instead.");
      });
  }

  if (window.visualViewport) {
    window.visualViewport.addEventListener('resize', syncMobileViewport);
    window.visualViewport.addEventListener('scroll', syncMobileViewport);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ buildWidget(); scheduleNudge(); });
  } else {
    buildWidget();
    scheduleNudge();
  }
})();
