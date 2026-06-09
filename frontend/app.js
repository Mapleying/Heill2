// Sportcation AI App Logic

// Global error display for debugging
window.addEventListener('error', function(event) {
    const errorBanner = document.createElement('div');
    errorBanner.style.position = 'fixed';
    errorBanner.style.top = '10px';
    errorBanner.style.left = '50%';
    errorBanner.style.transform = 'translateX(-50%)';
    errorBanner.style.background = 'rgba(239, 68, 68, 0.95)';
    errorBanner.style.color = 'white';
    errorBanner.style.padding = '14px 28px';
    errorBanner.style.borderRadius = '8px';
    errorBanner.style.zIndex = '10000';
    errorBanner.style.boxShadow = '0 8px 24px rgba(0,0,0,0.6)';
    errorBanner.style.fontFamily = 'sans-serif';
    errorBanner.style.fontSize = '14px';
    errorBanner.style.border = '1px solid rgba(255,255,255,0.2)';
    errorBanner.innerHTML = `<strong>JS Error:</strong> ${event.message} at ${event.filename.split('/').pop()}:${event.lineno}`;
    document.body.appendChild(errorBanner);
    setTimeout(() => errorBanner.remove(), 10000);
});

// Generate a random session ID if not exists
if (!sessionStorage.getItem('sportcation_session_id')) {
    sessionStorage.setItem('sportcation_session_id', 'sess_' + Math.random().toString(36).substring(2, 11));
}
const sessionId = sessionStorage.getItem('sportcation_session_id');

// State variables
let geminiApiKey = localStorage.getItem('gemini_api_key') || '';

// DOM Elements
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatHistory = document.getElementById('chat-history');
// Typing indicator lives inside chatHistory so it never pushes the footer
function showTypingIndicator() {
    const el = document.createElement('div');
    el.id = 'typing-indicator';
    el.classList.add('typing-indicator');
    el.innerHTML = '<span></span><span></span><span></span>';
    chatHistory.appendChild(el);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}
function hideTypingIndicator() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
}

const apiStatusBadge = document.getElementById('api-status-badge');
const btnSettings = document.getElementById('btn-settings');
const modalSettings = document.getElementById('modal-settings');
const btnCloseModal = document.getElementById('btn-close-modal');
const btnSaveSettings = document.getElementById('btn-save-settings');
const btnClearSettings = document.getElementById('btn-clear-settings');
const geminiKeyInput = document.getElementById('gemini-key-input');

// Itinerary Elements
const itineraryStatus = document.getElementById('itinerary-status');
const itineraryEmpty = document.getElementById('itinerary-empty');
const itineraryDetails = document.getElementById('itinerary-details');
const conflictWarnings = document.getElementById('conflict-warnings');

const itinCampName = document.getElementById('itin-camp-name');
const itinCampSport = document.getElementById('itin-camp-sport');
const itinCampLocation = document.getElementById('itin-camp-location');
const itinCampDates = document.getElementById('itin-camp-dates');
const itinCampPrice = document.getElementById('itin-camp-price');
const itinCampLink = document.getElementById('itin-camp-link');

const itinFlightCardEmpty = document.getElementById('itin-flight-card-empty');
const itinFlightCard = document.getElementById('itin-flight-card');
const itinFlightAirline = document.getElementById('itin-flight-airline');
const itinFlightRoute = document.getElementById('itin-flight-route');
const itinFlightDep = document.getElementById('itin-flight-dep');
const itinFlightPrice = document.getElementById('itin-flight-price');
const itinFlightLink = document.getElementById('itin-flight-link');

const itinHotelCardEmpty = document.getElementById('itin-hotel-card-empty');
const itinHotelCard = document.getElementById('itin-hotel-card');
const itinHotelName = document.getElementById('itin-hotel-name');
const itinHotelStars = document.getElementById('itin-hotel-stars');
const itinHotelPartner = document.getElementById('itin-hotel-partner');
const itinHotelPrice = document.getElementById('itin-hotel-price');
const itinHotelLink = document.getElementById('itin-hotel-link');

const itinTotalPrice = document.getElementById('itin-total-price');

const btnExportPdf = document.getElementById('btn-export-pdf');
const btnExportIcs = document.getElementById('btn-export-ics');

const btnTheme = document.getElementById('btn-theme');
const themeIcon = document.getElementById('theme-icon');

// Theme toggle logic
let isLightTheme = localStorage.getItem('theme') === 'light';
if (isLightTheme) {
    document.body.classList.add('light-theme');
    updateThemeIcon(true);
}

btnTheme.addEventListener('click', () => {
    isLightTheme = !isLightTheme;
    if (isLightTheme) {
        document.body.classList.add('light-theme');
        localStorage.setItem('theme', 'light');
        updateThemeIcon(true);
    } else {
        document.body.classList.remove('light-theme');
        localStorage.setItem('theme', 'dark');
        updateThemeIcon(false);
    }
});

function updateThemeIcon(light) {
    if (light) {
        // Sun icon SVG path
        themeIcon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
    } else {
        // Moon icon SVG path
        themeIcon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
    }
}

// Initialize UI
fetchServerConfig();
fetchCurrentItinerary();

async function fetchServerConfig() {
    try {
        const res = await fetch('/api/config');
        if (res.ok) {
            const cfg = await res.json();
            updateApiBadge(cfg.gemini_active);
        }
    } catch (e) {
        updateApiBadge(false);
    }
}

// Handle settings key save
btnSettings.addEventListener('click', () => {
    geminiKeyInput.value = geminiApiKey;
    modalSettings.classList.remove('hidden');
});

btnCloseModal.addEventListener('click', () => {
    modalSettings.classList.add('hidden');
});

btnSaveSettings.addEventListener('click', () => {
    geminiApiKey = geminiKeyInput.value.trim();
    localStorage.setItem('gemini_api_key', geminiApiKey);
    fetchServerConfig();
    modalSettings.classList.add('hidden');
});

btnClearSettings.addEventListener('click', () => {
    geminiApiKey = '';
    localStorage.removeItem('gemini_api_key');
    geminiKeyInput.value = '';
    fetchServerConfig();
    modalSettings.classList.add('hidden');
});

// Update API Mode Badge
// serverActive = true when server has GEMINI_API_KEY configured
function updateApiBadge(serverActive) {
    const active = serverActive || !!geminiApiKey;
    if (active) {
        apiStatusBadge.textContent = 'Gemini AI Active';
        apiStatusBadge.className = 'status-badge badge-live';
    } else {
        apiStatusBadge.textContent = 'Simulation Mode';
        apiStatusBadge.className = 'status-badge badge-simulation';
    }
}

// Fetch current itinerary state from backend
async function fetchCurrentItinerary() {
    try {
        const res = await fetch(`/api/itinerary/${sessionId}`);
        if (res.ok) {
            const data = await res.json();
            if (data.itinerary) {
                updateItineraryUI(data.itinerary);
            }
        }
    } catch (e) {
        console.error('Failed to load initial itinerary', e);
    }
}

// Safely escape text for HTML insertion
function escapeHtml(text) {
    const d = document.createElement('div');
    d.appendChild(document.createTextNode(String(text)));
    return d.innerHTML;
}

// Convert plain text with markdown to safe HTML
function renderMarkdown(text) {
    let html = escapeHtml(text)
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/### (.*?)(<br>|$)/g, '<h3>$1</h3>')
        .replace(/(?:^|(?<=<br>))- (.*?)(?=<br>|$)/g, '<li>$1</li>');
    return html.replace(/(<li>[\s\S]*?<\/li>)+/g, m => `<ul>${m}</ul>`);
}

// Append messages to chat interface
function appendMessage(sender, text) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message');
    messageDiv.classList.add(sender === 'user' ? 'user-message' : 'agent-message');
    messageDiv.innerHTML = `<div class="message-content">${renderMarkdown(text)}</div>`;
    chatHistory.appendChild(messageDiv);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Render clickable flight/hotel suggestion cards below the agent message
function renderSuggestions(suggestions) {
    const camps   = suggestions.filter(s => s.type === 'camp');
    const flights = suggestions.filter(s => s.type === 'flight');
    const hotels  = suggestions.filter(s => s.type === 'hotel');

    function makeSection(items, label) {
        if (!items.length) return null;
        const wrap = document.createElement('div');
        wrap.innerHTML = `<div class="suggestion-section-label">${label}</div>`;
        const row = document.createElement('div');
        row.classList.add('suggestions-row');

        items.forEach(s => {
            const card = document.createElement('div');
            card.classList.add('suggestion-card', `suggestion-${s.type}`);
            card.innerHTML = `
                <div class="sc-top">
                    <span class="sc-price">${escapeHtml(s.price)}</span>
                    ${s.booking_link
                        ? `<a href="${s.booking_link.replace(/"/g,'&quot;')}" target="_blank" rel="noopener" class="sc-book-link">Book ↗</a>`
                        : ''}
                </div>
                <span class="sc-label">${escapeHtml(s.label)}</span>
                <span class="sc-sub">${escapeHtml(s.sublabel || '')}</span>
                <span class="sc-hint">Click to add to itinerary</span>
            `;
            card.addEventListener('click', e => {
                if (!e.target.closest('.sc-book-link')) sendSuggestion(s.action);
            });
            row.appendChild(card);
        });

        wrap.appendChild(row);
        return wrap;
    }

    const container = document.createElement('div');
    container.classList.add('suggestions-container');
    const cs = makeSection(camps,   '⛺ Choose a Camp');
    const fs = makeSection(flights, '✈️ Flights');
    const hs = makeSection(hotels,  '🏨 Hotels');
    if (cs) container.appendChild(cs);
    if (fs) container.appendChild(fs);
    if (hs) container.appendChild(hs);

    chatHistory.appendChild(container);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Handle Form Submission — streaming version
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    chatInput.value = '';
    appendMessage('user', message);
    showTypingIndicator();

    let messageDiv = null;
    let contentDiv = null;
    let fullText = '';
    let firstChunk = true;

    try {
        const res = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message, session_id: sessionId, api_key: geminiApiKey || null })
        });

        if (!res.ok) {
            hideTypingIndicator();
            const errData = await res.json().catch(() => ({}));
            appendMessage('agent', `Sorry, something went wrong: ${errData.detail || 'Internal Error'}`);
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.startsWith('data: ')) continue;
                let data;
                try { data = JSON.parse(line.slice(6)); } catch { continue; }

                if (data.text) {
                    if (firstChunk) { hideTypingIndicator(); firstChunk = false; }
                    if (!messageDiv) {
                        messageDiv = document.createElement('div');
                        messageDiv.classList.add('message', 'agent-message');
                        contentDiv = document.createElement('div');
                        contentDiv.classList.add('message-content');
                        messageDiv.appendChild(contentDiv);
                        chatHistory.appendChild(messageDiv);
                    }
                    fullText += data.text;
                    contentDiv.innerHTML = renderMarkdown(fullText);
                    chatHistory.scrollTop = chatHistory.scrollHeight;
                }

                if (data.done) {
                    if (data.suggestions && data.suggestions.length) renderSuggestions(data.suggestions);
                    if (data.itinerary) updateItineraryUI(data.itinerary);
                }
            }
        }

        if (firstChunk) hideTypingIndicator(); // safety: hide if no text arrived
    } catch (error) {
        hideTypingIndicator();
        appendMessage('agent', 'Connection error. Please ensure the backend server is running.');
        console.error(error);
    }
});

// Update the Live Itinerary sidebar panel
function updateItineraryUI(itinerary) {
    if (!itinerary) {
        itineraryEmpty.classList.remove('hidden');
        itineraryDetails.classList.add('hidden');
        itineraryStatus.textContent = 'Empty';
        itineraryStatus.className = 'itinerary-status badge-draft';
        return;
    }
    
    itineraryEmpty.classList.add('hidden');
    itineraryDetails.classList.remove('hidden');
    itineraryStatus.textContent = 'Active Draft';
    itineraryStatus.className = 'itinerary-status badge-draft';
    
    // 1. Camp Anchor details
    const camp = itinerary.camp;
    const session = itinerary.session;
    itinCampName.textContent = camp.name;
    itinCampSport.textContent = camp.sport;
    itinCampLocation.textContent = `${camp.location.city}, ${camp.location.country_code}`;
    itinCampDates.textContent = `${session.start_date} to ${session.end_date}`;
    itinCampPrice.textContent = `€${session.price_per_person_eur.toFixed(2)}`;
    itinCampLink.href = camp.cancellation_policy ? '#' : '#'; // Deep link trigger
    
    // 2. Flight Details
    const flight = itinerary.flight;
    if (flight) {
        itinFlightCardEmpty.classList.add('hidden');
        itinFlightCard.classList.remove('hidden');
        
        itinFlightAirline.textContent = flight.airline;
        itinFlightRoute.innerHTML = `${flight.origin} &rarr; ${flight.destination}`;
        itinFlightDep.textContent = flight.departure_time;
        itinFlightPrice.textContent = `€${(flight.price_eur + flight.equipment_fee_eur).toFixed(2)} (inc. €${flight.equipment_fee_eur} equip)`;
        itinFlightLink.href = flight.booking_link;
    } else {
        itinFlightCardEmpty.classList.remove('hidden');
        itinFlightCard.classList.add('hidden');
    }
    
    // 3. Hotel Details
    const hotel = itinerary.hotel;
    if (hotel) {
        itinHotelCardEmpty.classList.add('hidden');
        itinHotelCard.classList.remove('hidden');
        
        itinHotelName.textContent = hotel.name;
        itinHotelStars.textContent = `${hotel.stars} ★`;
        itinHotelPrice.textContent = `€${hotel.price_per_night_eur.toFixed(2)}/night`;
        itinHotelLink.href = hotel.booking_link;
        
        if (hotel.sport_partner) {
            itinHotelPartner.classList.remove('hidden');
        } else {
            itinHotelPartner.classList.add('hidden');
        }
    } else {
        itinHotelCardEmpty.classList.remove('hidden');
        itinHotelCard.classList.add('hidden');
    }
    
    // 4. Conflicts
    if (itinerary.conflict_warnings && itinerary.conflict_warnings.length > 0) {
        conflictWarnings.classList.remove('hidden');
        conflictWarnings.innerHTML = '⚠️ <strong>Travel Alerts:</strong><br>' + 
            itinerary.conflict_warnings.map(w => `- ${w}`).join('<br>');
    } else {
        conflictWarnings.classList.add('hidden');
    }
    
    // 5. Total Price
    itinTotalPrice.textContent = `€${itinerary.total_price_eur.toFixed(2)}`;
}

// Chip suggestions helper
window.sendSuggestion = function(text) {
    chatInput.value = text;
    chatForm.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
};

// Export buttons click handlers
btnExportPdf.addEventListener('click', () => {
    window.open(`/api/export/${sessionId}/pdf`, '_blank');
});

btnExportIcs.addEventListener('click', () => {
    window.open(`/api/export/${sessionId}/ics`, '_blank');
});
