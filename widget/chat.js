// CartPilot embeddable chat widget.
let sessionId = null;

const fab = document.getElementById('chatfab');
const panel = document.getElementById('chatpanel');
const log = document.getElementById('chatlog');
const form = document.getElementById('chatform');
const input = document.getElementById('chatinput');

fab.onclick = () => {
  panel.classList.toggle('open');
  if (panel.classList.contains('open') && !log.children.length) {
    addMsg('bot', 'Hi! Tell me what you are shopping for — a gift, something for home?');
  }
};

function addMsg(who, text) {
  const d = document.createElement('div');
  d.className = 'msg ' + who;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}

form.onsubmit = async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addMsg('user', text);
  input.value = '';
  addMsg('bot', '…');
  const thinking = log.lastChild;
  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({session_id: sessionId, message: text}),
    });
    const data = await res.json();
    sessionId = data.session_id;
    thinking.textContent = data.reply;
  } catch (err) {
    thinking.textContent = 'Something broke talking to the server. (Check the console.)';
  }
  log.scrollTop = log.scrollHeight;
};

// Render the product grid from the API.
fetch('/api/products').then(r => r.json()).then(data => {
  const grid = document.getElementById('grid');
  grid.innerHTML = data.products.map(p =>
    `<div class="card"><h3>${p.name}</h3><p>${p.description}</p><div class="price">₹${(p.price_paise/100).toLocaleString('en-IN')}</div></div>`
  ).join('');
});
