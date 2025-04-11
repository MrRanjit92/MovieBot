const form = document.getElementById('chat-form');
const input = document.getElementById('user-input');
const chatBox = document.getElementById('chat-box');
const userEmailDisplay = document.getElementById('user-email');

// Load from localStorage
const token = localStorage.getItem('token');
const userId = localStorage.getItem('userId');

// Auto-redirect if not logged in
if (!token || !userId) {
  window.location.href = '/';
}

// Get user email from JWT payload (optional enhancement)
try {
  const payload = JSON.parse(atob(token.split('.')[1]));
  userEmailDisplay.innerText = payload.email || 'User';
} catch (e) {
  userEmailDisplay.innerText = 'User';
}

// Fetch chat history
window.addEventListener('load', async () => {
  try {
    const res = await axios.get('/chat-history', {
      headers: { 'x-access-token': token }
    });
    const chats = res.data.chats.reverse(); // newest last
    chats.forEach(chat => {
      appendMessage(chat.sender === 'user' ? 'user' : 'bot', chat.message);
    });
  } catch (err) {
    appendMessage('bot', "⚠️ Couldn't load chat history.");
  }
});

// Handle new messages
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const userMessage = input.value.trim();
  if (!userMessage) return;

  appendMessage('user', userMessage);
  input.value = '';
  showTyping();

  try {
    const res = await axios.post('/recommend', { prompt: userMessage }, {
      headers: { 'x-access-token': token }
    });

    removeTyping();
    const recs = res.data.recommendations;
    let reply = "";

    if (!recs.length) {
      reply = "Hmm... I couldn’t find any good recommendations 😕";
    } else {
      reply = recs.map(r => `🎬 <b>${r.title}</b> (${r.genres}) – ⭐ ${r.predicted_rating}`).join('<br>');
    }

    appendMessage('bot', reply);
  } catch (err) {
    removeTyping();
    appendMessage('bot', "⚠️ Something went wrong.");
  }
});

function appendMessage(sender, text) {
  const div = document.createElement('div');
  div.className = sender === 'user' ? 'user-message d-block ms-auto' : 'bot-message d-block';
  div.innerHTML = text;
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function showTyping() {
  const typing = document.createElement('div');
  typing.className = 'bot-message typing';
  typing.id = 'typing';
  typing.innerHTML = '🤖 typing...';
  chatBox.appendChild(typing);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTyping() {
  const typing = document.getElementById('typing');
  if (typing) typing.remove();
}


// Logout button
document.getElementById('logout-btn').addEventListener('click', () => {
  localStorage.removeItem('token');
  localStorage.removeItem('userId');
  window.location.href = '/';
});
