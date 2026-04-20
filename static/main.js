document.addEventListener("DOMContentLoaded", () => {
  const lapCurrentEl = document.getElementById("lap-current");
  const lapTotalEl = document.getElementById("lap-total");
  const safetyCarEl = document.getElementById("safety-car");
  const podiumEl = document.getElementById("podium");
  const driverListEl = document.getElementById("driver-list");

  const eventSource = new EventSource("/api/live-events");

  eventSource.onmessage = function (event) {
    const data = JSON.parse(event.data);

    updateRaceInfo(data);
    updatePodium(data.top3 || []);
    updateDriverList(data.standings || []);
  };

  eventSource.onerror = function () {
    console.error("Eroare la conexiunea SSE /api/live-events");
  };

  function updateRaceInfo(data) {
    if (lapCurrentEl) {
      lapCurrentEl.textContent =
        data.lap_current !== null && data.lap_current !== undefined
          ? data.lap_current
          : "-";
    }

    if (lapTotalEl) {
      lapTotalEl.textContent =
        data.lap_total !== null && data.lap_total !== undefined
          ? data.lap_total
          : "-";
    }

    if (safetyCarEl) {
      safetyCarEl.textContent = data.safety_car ? "Yes" : "No";
    }
  }

  function updatePodium(top3) {
    if (!podiumEl) return;

    const first = top3[0] || null;
    const second = top3[1] || null;
    const third = top3[2] || null;

    podiumEl.innerHTML = `
      ${buildPodiumCard(2, second, "place-2")}
      ${buildPodiumCard(1, first, "place-1")}
      ${buildPodiumCard(3, third, "place-3")}
    `;
  }

  function buildPodiumCard(place, driver, className) {
    const code = driver?.code ?? "-";
    const probability =
      driver?.prob_winner !== undefined && driver?.prob_winner !== null
        ? `${(Number(driver.prob_winner) * 100).toFixed(1)}%`
        : "-";

    return `
      <div class="podium-card ${className}">
        <span class="place">${place}</span>
        <h4>${code}</h4>
        <p>Win probability</p>
        <strong>${probability}</strong>
      </div>
    `;
  }

function updateDriverList(standings) {
  if (!driverListEl) return;

  if (!standings.length) {
    driverListEl.innerHTML = `
      <div class="driver-row">
        <span>No live data yet</span>
        <span>-</span>
      </div>
    `;
    return;
  }

  // eliminam primii 3 (podium)
  const rest = standings.slice(3, 7); // urmatorii 4

  driverListEl.innerHTML = rest
    .map((driver) => {
      const code = driver.code ?? "-";
      const probability =
        driver.prob_winner !== undefined && driver.prob_winner !== null
          ? `${(Number(driver.prob_winner) * 100).toFixed(1)}%`
          : "-";

      return `
        <div class="driver-row">
          <span>${code}</span>
          <span>${probability}</span>
        </div>
      `;
    })
    .join("");
}
});