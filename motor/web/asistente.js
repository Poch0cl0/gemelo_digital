(() => {
  const $ = id => document.getElementById(id);
  const messages = $('chat-messages');
  const form = $('chat-form');
  const input = $('chat-input');
  const sendBtn = $('chat-send');
  const statusEl = $('agent-status');
  const errorEl = $('agent-error');
  const history = [];

  const make = (tag, props = {}, children = []) => {
    const n = Object.assign(document.createElement(tag), props);
    [].concat(children).forEach(c => n.append(c));
    return n;
  };

  function showError(text) {
    errorEl.hidden = !text;
    errorEl.textContent = text || '';
  }

  function appendBubble(role, text, tools) {
    const bubble = make('div', {className: `chat-bubble ${role}`});
    bubble.append(make('p', {textContent: text}));
    if (tools && tools.length) {
      const meta = make('div', {className: 'chat-tools'});
      meta.textContent = 'Herramientas consultadas: ' + tools.join(', ');
      bubble.append(meta);
    }
    messages.append(bubble);
    messages.scrollTop = messages.scrollHeight;
  }

  async function loadStatus() {
    try {
      const res = await fetch('/api/agent/status');
      const data = await res.json();
      if (data.available) {
        const prov = data.provider ? ' · ' + data.provider : '';
        let lf = '';
        if (data.langflow?.reachable) {
          lf = ' · LangFlow';
        } else if (data.langflow?.configured) {
          lf = ' · LangFlow sin conexión';
        }
        statusEl.textContent = '● Asistente listo' + prov + lf + (data.trained_utc ? ' · informe ' + new Date(data.trained_utc).toLocaleString('es-PE') : '');
        showError('');
      } else {
        statusEl.textContent = '● Asistente no disponible';
        showError(data.message || 'El asistente no está disponible.');
        sendBtn.disabled = true;
      }
    } catch {
      statusEl.textContent = '● Error de conexión';
      showError('No se pudo contactar con el servidor.');
      sendBtn.disabled = true;
    }
  }

  form.addEventListener('submit', async ev => {
    ev.preventDefault();
    const question = input.value.trim();
    if (!question) return;
    showError('');
    appendBubble('user', question);
    history.push({role: 'user', content: question});
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;
    const pending = make('div', {className: 'chat-bubble assistant pending', textContent: 'Consultando informe…'});
    messages.append(pending);
    messages.scrollTop = messages.scrollHeight;
    try {
      const res = await fetch('/api/agent/chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question, history}),
      });
      const data = await res.json();
      pending.remove();
      if (!res.ok) throw new Error(data.error || 'Error al consultar el asistente.');
      appendBubble('assistant', data.answer, data.tools_used);
      history.push({role: 'assistant', content: data.answer});
    } catch (err) {
      pending.remove();
      showError(err.message);
    } finally {
      input.disabled = false;
      sendBtn.disabled = false;
      input.focus();
    }
  });

  loadStatus();
})();
