// public/widget.js

// --- COOKIE UTILITY ---
function setCookie(name, value, days) {
  const expires = new Date(Date.now() + days * 864e5).toUTCString();
  document.cookie = name + '=' + encodeURIComponent(value) + '; expires=' + expires + '; path=/';
}

function getCookie(name) {
  return document.cookie.split('; ').reduce((r, v) => {
    const parts = v.split('=');
    return parts[0] === name ? decodeURIComponent(parts[1]) : r;
  }, '');
}

function deleteCookie(name) {
  document.cookie = name + '=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
}

// guestInfo di default
let guestInfo = {
  propertyId: "CT-01",
  locale: "it",
  arrival_date: null,
  last_name: null
};

// 1) PRIMA cosa: prova a leggere il cookie
const cookieData = getCookie("concierge_guest");
if (cookieData) {
  try {
    guestInfo = JSON.parse(cookieData);
    console.log("Ospite riconosciuto dal cookie:", guestInfo);
  } catch (e) {
    console.warn("Cookie concierge_guest non valido, lo elimino");
    deleteCookie("concierge_guest");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const widget = document.getElementById("concierge-widget");
  const loginBox = document.getElementById("guest-login");
  const msgBox = document.getElementById("cw-messages");
  const form = document.getElementById("cw-form");

  if (widget.dataset.propertyId) {
    guestInfo.propertyId = widget.dataset.propertyId;
  }

  if (widget.dataset.locale) {
    guestInfo.locale = widget.dataset.locale;
  }

  // se non abbiamo i dati, mostra login e nascondi chat
  if (!guestInfo.arrival_date || !guestInfo.last_name) {
    loginBox.style.display = "block";
    msgBox.style.display = "none";
    form.style.display = "none";
  } else {
    // già identificato
    loginBox.style.display = "none";
    msgBox.style.display = "block";
    form.style.display = "flex";
  }

  // gestore login
  document.getElementById("login-btn").addEventListener("click", async () => {
    const lastname = document.getElementById("login-lastname").value.trim();
    const date = document.getElementById("login-date").value;

    if (!lastname || !date) {
      alert("Inserisci cognome e data di arrivo.");
      return;
    }

    try {
      const res = await fetch("/api/match-guest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          property_id: guestInfo.propertyId,
          arrival_date: date,
          last_name: lastname
        })
      });

      const payload = await res.json().catch(() => null);

      if (!res.ok) {
        const errMsg = payload?.message || "Prenotazione non trovata.";
        alert(errMsg);
        return;
      }

      if (!payload || payload.status !== "ok") {
        const statusMsg = payload?.message || "Prenotazione non trovata.";
        alert(statusMsg);
        return;
      }

      // se va bene, salviamo i dati
      guestInfo.arrival_date = date;
      guestInfo.last_name = lastname;
      guestInfo.propertyId = widget.dataset.propertyId || guestInfo.propertyId;
      guestInfo.locale = widget.dataset.locale || guestInfo.locale;
      setCookie("concierge_guest", JSON.stringify(guestInfo), 7);

      // mostra la chat
      loginBox.style.display = "none";
      msgBox.style.display = "block";
      form.style.display = "flex";

      appendMessage(`Ciao ${lastname}, ho trovato la tua prenotazione del ${date}.`, "bot");
    } catch (err) {
      console.error(err);
      alert("Errore di connessione al server.");
    }
  });

  // --- CHAT ORIGINALE ---
  const API_URL = "/api/chat";
  const propertyId = guestInfo.propertyId || widget.dataset.propertyId || "CT-01";
  const locale = guestInfo.locale || widget.dataset.locale || "it";
  const input = document.getElementById("cw-input");

  function appendMessage(text, from = "bot") {
    const div = document.createElement("div");
    div.classList.add("cw-msg");
    if (from === "bot") div.classList.add("cw-msg-bot");
    else div.classList.add("cw-msg-user");
    div.textContent = text;
    msgBox.appendChild(div);
    msgBox.scrollTop = msgBox.scrollHeight;
    return div;
  }

  document.getElementById("cw-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    input.value = "";

    const loading = appendMessage("Sto controllando le informazioni…", "bot");
    loading.classList.add("cw-msg-loading");

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          propertyId: propertyId,
          locale: locale,
          arrival_date: guestInfo.arrival_date,
          last_name: guestInfo.last_name
        })
      });

      const data = await res.json();
      loading.remove();

      if (data && data.text) {
        appendMessage(data.text, "bot");
      } else {
        appendMessage("Non ho trovato una risposta nei dati disponibili. Contatto l’host.", "bot");
      }
    } catch (err) {
      console.error(err);
      loading.remove();
      appendMessage("C'è stato un problema di rete con il concierge.", "bot");
    }
  });
});
