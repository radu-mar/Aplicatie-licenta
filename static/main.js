document.addEventListener("DOMContentLoaded", () => {
  const lapCurrentEl = document.getElementById("lap-current");
  const lapTotalEl = document.getElementById("lap-total");
  const safetyCarEl = document.getElementById("safety-car");
  const podiumEl = document.getElementById("podium");
  const driverListEl = document.getElementById("driver-list");
  const liveFeedEl = document.getElementById("live-feed");

  const hlsUrl = "http://127.0.0.1:8080/stream.m3u8";
  let hlsInstance = null;
  let retryCount = 0;
  let retryTimer = null;

  initLiveStream();
  loadMomentumDrivers();
  loadDriversPage();

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

  function initLiveStream() {
    if (!liveFeedEl) return;

    clearRetry();

    if (hlsInstance) {
      hlsInstance.destroy();
      hlsInstance = null;
    }

    if (liveFeedEl.canPlayType("application/vnd.apple.mpegurl")) {
      liveFeedEl.src = `${hlsUrl}?t=${Date.now()}`;

      liveFeedEl.onloadedmetadata = () => {
        retryCount = 0;
        liveFeedEl.play().catch((err) => {
          console.error("Eroare play video nativ:", err);
        });
      };

      liveFeedEl.onerror = () => {
        scheduleRetry();
      };

      return;
    }

    if (window.Hls && Hls.isSupported()) {
      hlsInstance = new Hls({
        enableWorker: true,
        lowLatencyMode: true
      });

      hlsInstance.loadSource(`${hlsUrl}?t=${Date.now()}`);
      hlsInstance.attachMedia(liveFeedEl);

      hlsInstance.on(Hls.Events.MANIFEST_PARSED, function () {
        retryCount = 0;
        liveFeedEl.play().catch((err) => {
          console.error("Eroare la pornirea streamului video:", err);
        });
      });

      hlsInstance.on(Hls.Events.ERROR, function (event, data) {
        console.error("Eroare HLS:", data);

        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              scheduleRetry();
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              try {
                hlsInstance.recoverMediaError();
              } catch (e) {
                scheduleRetry();
              }
              break;
            default:
              scheduleRetry();
              break;
          }
        }
      });

      liveFeedEl.onerror = () => {
        scheduleRetry();
      };

      return;
    }

    console.error("Browserul nu suporta HLS.");
  }

  function scheduleRetry() {
    clearRetry();

    retryCount += 1;
    const delay = Math.min(2000 + retryCount * 1000, 8000);

    console.warn(`Stream indisponibil. Reincerc in ${delay} ms...`);

    retryTimer = setTimeout(() => {
      initLiveStream();
    }, delay);
  }

  function clearRetry() {
    if (retryTimer) {
      clearTimeout(retryTimer);
      retryTimer = null;
    }
  }

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

  async function loadMomentumDrivers() {
    try {
      const response = await fetch("/api/momentum");
      const data = await response.json();

      const cardTitle = document.getElementById("momentum-card-title");
      const mainContainer = document.getElementById("momentum-main");
      const detailsContainer = document.getElementById("momentum-details");

      if (!Array.isArray(data) || data.length === 0) {
        if (mainContainer) {
          mainContainer.innerHTML = `
            <div class="momentum-icon">🏁</div>
            <p class="momentum-label">Highest current momentum</p>
            <h4>-</h4>
            <span>Momentum: -</span>
          `;
        }

        if (detailsContainer) {
          detailsContainer.innerHTML = `
            <div class="momentum-row">
              <span>2nd place</span>
              <strong>-</strong>
            </div>
            <div class="momentum-row">
              <span>3rd place</span>
              <strong>-</strong>
            </div>
          `;
        }
        return;
      }

      if (cardTitle) {
        cardTitle.textContent = "Top Momentum Drivers";
      }

      const first = data[0];
      const second = data[1];
      const third = data[2];

      if (mainContainer) {
        mainContainer.innerHTML = `
          <div class="momentum-icon">🏁</div>
          <p class="momentum-label">Highest current momentum</p>
          <h4>${first ? first.code : "-"}</h4>
          <span>Momentum: ${first ? first.momentum : "-"}</span>
        `;
      }

      let detailsHtml = "";

      if (second) {
        detailsHtml += `
          <div class="momentum-row">
            <span>2nd place</span>
            <strong>${second.code} (${second.momentum})</strong>
          </div>
        `;
      }

      if (third) {
        detailsHtml += `
          <div class="momentum-row">
            <span>3rd place</span>
            <strong>${third.code} (${third.momentum})</strong>
          </div>
        `;
      }

      if (detailsContainer) {
        detailsContainer.innerHTML = detailsHtml;
      }

    } catch (error) {
      console.error("Eroare la momentum drivers:", error);
    }
  }

  async function loadDriversPage() {
    const driversGrid = document.getElementById("drivers-grid");
    if (!driversGrid) return;

    const driverNumbers = {
      VER: 1, PER: 11, HAM: 44, RUS: 63, LEC: 16, SAI: 55,
      ALO: 14, STR: 18, NOR: 4, PIA: 81, OCO: 31, GAS: 10,
      ALB: 23, SAR: 2, BOT: 77, ZHO: 24, MAG: 20, HUL: 27,
      TSU: 22, DEV: 21, RIC: 3, LAW: 40
    };

    const driverNames = {
      VER: "Max Verstappen",
      PER: "Sergio Perez",
      HAM: "Lewis Hamilton",
      RUS: "George Russell",
      LEC: "Charles Leclerc",
      SAI: "Carlos Sainz",
      ALO: "Fernando Alonso",
      STR: "Lance Stroll",
      NOR: "Lando Norris",
      PIA: "Oscar Piastri",
      OCO: "Esteban Ocon",
      GAS: "Pierre Gasly",
      ALB: "Alexander Albon",
      SAR: "Logan Sargeant",
      BOT: "Valtteri Bottas",
      ZHO: "Guanyu Zhou",
      MAG: "Kevin Magnussen",
      HUL: "Nico Hulkenberg",
      TSU: "Yuki Tsunoda",
      DEV: "Nyck de Vries",
      RIC: "Daniel Ricciardo",
      LAW: "Liam Lawson"
    };

    try {
      const response = await fetch("/api/drivers");
      const drivers = await response.json();

      if (!Array.isArray(drivers) || drivers.length === 0) {
        driversGrid.innerHTML = `
          <div class="driver-card">
            <div class="driver-top">
              <div class="driver-avatar">--</div>
              <div>
                <h4>No data</h4>
                <p>Drivers dataset is empty</p>
              </div>
            </div>
          </div>
        `;
        return;
      }

      driversGrid.innerHTML = drivers.map(driver => {
        const driverNumber = driverNumbers[driver.code] ?? "--";
        const fullName = driverNames[driver.code] ?? driver.code ?? "-";

        return `
          <div class="driver-card">
            <div class="driver-top">
              <div class="driver-avatar">${driver.code ?? "--"}</div>
              <div>
                <h4>${fullName}</h4>
                <p>Driver profile</p>
              </div>
            </div>

            <div class="driver-number">#${driverNumber}</div>

            <div class="driver-stats-grid">
              <div>
                <span>Code</span>
                <strong>${driver.code ?? "-"}</strong>
              </div>
              <div>
                <span>Driver accident rate</span>
                <strong>${driver.rata_accidente_pilot ?? "-"}%</strong>
              </div>
              <div>
                <span>Pilot momentum</span>
                <strong>${driver.pilot_momentum ?? "-"}</strong>
              </div>
              <div>
                <span>Meaning</span>
                <strong>Average points in last 3 races</strong>
              </div>
            </div>
          </div>
        `;
      }).join("");

    } catch (error) {
      console.error("Eroare la incarcarea driverilor:", error);
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

    const rest = standings.slice(3, 7);

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