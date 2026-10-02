let sessionId = null;
let isLoading = false;
const API_BASE_URL = window.location.protocol === 'file:' || ['localhost', '127.0.0.1'].includes(window.location.hostname)
    ? 'http://localhost:8000'
    : '';

const chatArea = document.getElementById('chatArea');
const messagesContainer = document.getElementById('messagesContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const welcomeCard = document.getElementById('welcomeCard');

messageInput.addEventListener('input', () => {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 120) + 'px';
});

messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

function sendExample(btn) {
    messageInput.value = btn.textContent;
    sendMessage();
}

async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || isLoading) return;

    if (welcomeCard) {
        welcomeCard.style.display = 'none';
    }

    appendUserMessage(text);
    messageInput.value = '';
    messageInput.style.height = 'auto';

    isLoading = true;
    sendBtn.disabled = true;
    const typingEl = showTypingIndicator();

    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                session_id: sessionId,
            }),
        });

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        sessionId = data.session_id;

        typingEl.remove();
        appendBotMessage(data);

    } catch (err) {
        typingEl.remove();
        const errorMessage = err instanceof TypeError
            ? `Cannot reach the API at ${API_BASE_URL}. Start the backend with "uvicorn backend.main:app --reload --port 8000" and open http://localhost:8000.`
            : err.message;
        appendBotError(errorMessage);
    } finally {
        isLoading = false;
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

function appendUserMessage(text) {
    const div = document.createElement('div');
    div.className = 'message message-user';
    div.innerHTML = `<div class="message-bubble">${escapeHtml(text)}</div>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function appendBotMessage(data) {
    const div = document.createElement('div');
    div.className = 'message message-bot';

    const formattedResponse = formatResponse(data.response);

    let sopBadge = '';
    if (data.cited_sop_id && data.matched_sops && data.matched_sops.length > 0) {
        const sop = data.matched_sops[0];
        const severity = sop.severity || 'low';
        sopBadge = `
            <div class="sop-badge severity-${severity}">
                📋 ${data.cited_sop_id} · ${sop.title} · ${severity.toUpperCase()}
            </div>
        `;
    } else if (!data.cited_sop_id) {
        sopBadge = `
            <div class="sop-badge severity-low">
                ℹ️ No specific policy applied
            </div>
        `;
    }

    let weatherPanel = '';
    if (data.weather_data && Object.keys(data.weather_data).length > 0) {
        const items = formatWeatherData(data.weather_data);
        weatherPanel = `
            <details class="weather-panel">
                <summary>Live Weather Data</summary>
                <div class="weather-grid">${items}</div>
            </details>
        `;
    }

    div.innerHTML = `
        <div class="bot-avatar">🌤</div>
        <div class="message-bubble">
            ${formattedResponse}
            ${sopBadge}
            ${weatherPanel}
        </div>
    `;

    messagesContainer.appendChild(div);
    scrollToBottom();
}

function appendBotError(errorMsg) {
    const div = document.createElement('div');
    div.className = 'message message-bot';
    div.innerHTML = `
        <div class="bot-avatar">⚠️</div>
        <div class="message-bubble" style="border-color: rgba(240, 85, 85, 0.3);">
            <p>Sorry, I encountered an error: ${escapeHtml(errorMsg)}</p>
            <p>Please try again in a moment.</p>
        </div>
    `;
    messagesContainer.appendChild(div);
    scrollToBottom();
}

function showTypingIndicator() {
    const div = document.createElement('div');
    div.className = 'typing-indicator';
    div.innerHTML = `
        <div class="bot-avatar">🌤</div>
        <div class="typing-dots">
            <span></span><span></span><span></span>
        </div>
    `;
    messagesContainer.appendChild(div);
    scrollToBottom();
    return div;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatResponse(text) {
    return text
        .split(/\n\n+/)
        .map(para => `<p>${para.replace(/\n/g, '<br>')}</p>`)
        .join('');
}

function formatWeatherData(data) {
    const labels = {
        temperature_2m: ['🌡️ Temperature', '°C'],
        wind_speed_10m: ['💨 Wind Speed', ' km/h'],
        wind_gusts_10m: ['🌬️ Wind Gusts', ' km/h'],
        precipitation: ['🌧️ Precipitation', ' mm'],
        precipitation_probability: ['☔ Precip. Probability', '%'],
        uv_index: ['☀️ UV Index', ''],
        relative_humidity_2m: ['💧 Humidity', '%'],
        visibility: ['👁️ Visibility', ' m'],
        us_aqi: ['🏭 Air Quality (AQI)', ''],
        current_hour: ['🕐 Local Hour', ''],
    };

    return Object.entries(data)
        .filter(([key]) => labels[key])
        .map(([key, val]) => {
            const [label, unit] = labels[key];
            return `
                <div class="weather-item">
                    <span class="weather-label">${label}</span>
                    <span class="weather-value">${val}${unit}</span>
                </div>
            `;
        })
        .join('');
}

function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
}
