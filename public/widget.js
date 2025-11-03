// public/widget.js
(function() {
  const widget = document.getElementById("concierge-widget");
  const msgBox = document.getElementById("cw-messages");
  const form = document.getElementById("cw-form");
  const input = document.getElementById("cw-input");

  const propertyId = widget.dataset.propertyId || "CT-01";
  const locale = widget.dataset.locale || "it";

  // cambia questo se lo monti su un dominio diverso
  const API_URL = "/api/chat";

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

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    // mostra messaggio utente
    appendMessage(text, "user");
    input.value = "";

    // messaggio di attesa
    const loading = appendMessage("Sto controllando le informazioni…", "bot");
    loading.classList.add("cw-msg-loading");

    try {
      const res = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          message: text,
          propertyId: propertyId,
          locale: locale
          // se in futuro vuoi passare anche cognome e data arrivo:
          // arrival_date: "2025-11-03",
          // last_name: "Rossi"
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
})();

