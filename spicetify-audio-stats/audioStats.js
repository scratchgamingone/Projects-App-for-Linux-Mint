// NAME: AudioStats & Sample Analytics
// AUTHOR: Sam
// DESCRIPTION: Real-time Audio Features HUD, Session Distribution Statistics (Mean, Std Dev, Correlation), and CSV Export for Spotify
// VERSION: 1.0.0

(function AudioStats() {
  const SCRIPT_NAME = "AudioStats";
  const STORAGE_KEY_SESSION = "spicetify_audiostats_session_tracks";
  const STORAGE_KEY_CACHE = "spicetify_audiostats_feature_cache";
  const MAX_CACHE_SIZE = 500;

  // Wait for Spicetify core modules to be ready
  if (
    !Spicetify ||
    !Spicetify.Player ||
    !Spicetify.Platform ||
    !Spicetify.Topbar ||
    !Spicetify.PopupModal
  ) {
    setTimeout(AudioStats, 300);
    return;
  }

  // Musical Key Lookups
  const PITCH_CLASSES = [
    "C", "C♯/D♭", "D", "D♯/E♭", "E", "F",
    "F♯/G♭", "G", "G♯/A♭", "A", "A♯/B♭", "B"
  ];

  // Camelot wheel dictionary: key_index (0-11) + mode (0=minor, 1=major) -> Camelot code
  const CAMELOT_MAP = {
    // Major (mode = 1) -> B
    "0_1": "8B",  "1_1": "3B",  "2_1": "10B", "3_1": "5B",
    "4_1": "12B", "5_1": "7B",  "6_1": "2B",  "7_1": "9B",
    "8_1": "4B",  "9_1": "11B", "10_1": "6B", "11_1": "1B",
    // Minor (mode = 0) -> A
    "0_0": "5A",  "1_0": "12A", "2_0": "7A",  "3_0": "2A",
    "4_0": "9A",  "5_0": "4A",  "6_0": "11A", "7_0": "6A",
    "8_0": "1A",  "9_0": "8A",  "10_0": "3A", "11_0": "10A"
  };

  // State
  let currentTrackId = null;
  let currentFeatures = null;
  let sessionTracks = loadSessionTracks();
  let featureCache = loadFeatureCache();
  let hudElement = null;

  // Storage Helpers
  function loadSessionTracks() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY_SESSION);
      return raw ? JSON.parse(raw) : [];
    } catch (e) {
      console.warn(`[${SCRIPT_NAME}] Failed to parse session tracks:`, e);
      return [];
    }
  }

  function saveSessionTracks() {
    try {
      localStorage.setItem(STORAGE_KEY_SESSION, JSON.stringify(sessionTracks));
    } catch (e) {
      console.warn(`[${SCRIPT_NAME}] Failed to save session tracks:`, e);
    }
  }

  function loadFeatureCache() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY_CACHE);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function saveFeatureCache() {
    try {
      const keys = Object.keys(featureCache);
      if (keys.length > MAX_CACHE_SIZE) {
        // Trim oldest half
        for (let i = 0; i < keys.length - MAX_CACHE_SIZE + 50; i++) {
          delete featureCache[keys[i]];
        }
      }
      localStorage.setItem(STORAGE_KEY_CACHE, JSON.stringify(featureCache));
    } catch (e) {
      console.warn(`[${SCRIPT_NAME}] Failed to save cache:`, e);
    }
  }

  // Auth Header Builder for Spotify Internal Endpoints
  function getAuthHeaders() {
    try {
      const token =
        Spicetify.Platform?.AuthorizationAPI?.getState()?.token?.accessToken ||
        Spicetify.Platform?.Session?.accessToken;
      return {
        Authorization: `Bearer ${token}`,
        "Spotify-App-Version": Spicetify.Platform?.version || "",
        "App-Platform": Spicetify.Platform?.PlatformData?.app_platform || "web",
        Accept: "application/json"
      };
    } catch (err) {
      console.error(`[${SCRIPT_NAME}] Error retrieving token:`, err);
      return {};
    }
  }

  // Audio Features Fetcher
  async function fetchAudioFeatures(trackId) {
    if (!trackId) return null;
    if (featureCache[trackId]) {
      return featureCache[trackId];
    }

    try {
      const url = `https://spclient.wg.spotify.com/audio-attributes/v1/audio-features/${trackId}?format=json`;
      const response = await fetch(url, { headers: getAuthHeaders() });

      if (!response.ok) {
        console.warn(`[${SCRIPT_NAME}] spclient audio-features responded with status ${response.status}`);
        return null;
      }

      const data = await response.json();
      if (!data || data.tempo == null) return null;

      const normalized = {
        id: trackId,
        tempo: Math.round(data.tempo * 10) / 10,
        key: data.key,
        mode: data.mode, // 1 = Major, 0 = Minor
        danceability: Math.round(data.danceability * 1000) / 1000,
        energy: Math.round(data.energy * 1000) / 1000,
        valence: Math.round(data.valence * 1000) / 1000,
        acousticness: Math.round(data.acousticness * 1000) / 1000,
        instrumentalness: Math.round(data.instrumentalness * 1000) / 1000,
        liveness: Math.round(data.liveness * 1000) / 1000,
        loudness: Math.round(data.loudness * 10) / 10,
        speechiness: Math.round(data.speechiness * 1000) / 1000,
        time_signature: data.time_signature
      };

      featureCache[trackId] = normalized;
      saveFeatureCache();
      return normalized;
    } catch (error) {
      console.error(`[${SCRIPT_NAME}] Failed to fetch audio features:`, error);
      return null;
    }
  }

  // Key & Mode String Formatters
  function formatKeyAndMode(keyIndex, mode) {
    if (keyIndex == null || keyIndex < 0 || keyIndex > 11) {
      return { note: "Unknown", modeStr: "", camelot: "--", full: "Unknown Key" };
    }
    const note = PITCH_CLASSES[keyIndex];
    const modeStr = mode === 1 ? "Major" : "Minor";
    const camelotKey = `${keyIndex}_${mode}`;
    const camelot = CAMELOT_MAP[camelotKey] || "--";
    return {
      note,
      modeStr,
      camelot,
      full: `${note} ${modeStr} (${camelot})`
    };
  }

  function getHarmonicNeighbors(camelot) {
    if (!camelot || camelot === "--") return [];
    const num = parseInt(camelot);
    const letter = camelot.slice(-1);
    const otherLetter = letter === "A" ? "B" : "A";
    const prevNum = num === 1 ? 12 : num - 1;
    const nextNum = num === 12 ? 1 : num + 1;

    return [
      { code: `${num}${letter}`, type: "Same Key (Harmonic)" },
      { code: `${prevNum}${letter}`, type: "-1 Step (Subdominant)" },
      { code: `${nextNum}${letter}`, type: "+1 Step (Dominant)" },
      { code: `${num}${otherLetter}`, type: `Relative ${otherLetter === "A" ? "Minor" : "Major"}` }
    ];
  }

  // Statistical Calculation Engine
  function calculateSummaryStats(arr) {
    if (!arr || arr.length === 0) {
      return { n: 0, mean: 0, std: 0, min: 0, max: 0 };
    }
    const n = arr.length;
    const mean = arr.reduce((acc, val) => acc + val, 0) / n;
    const variance =
      n > 1
        ? arr.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / (n - 1)
        : 0;
    const std = Math.sqrt(variance);
    const min = Math.min(...arr);
    const max = Math.max(...arr);
    return {
      n,
      mean: Math.round(mean * 1000) / 1000,
      std: Math.round(std * 1000) / 1000,
      min: Math.round(min * 1000) / 1000,
      max: Math.round(max * 1000) / 1000
    };
  }

  function calculatePearsonCorrelation(xs, ys) {
    if (!xs || !ys || xs.length < 2 || xs.length !== ys.length) return null;
    const n = xs.length;
    const meanX = xs.reduce((a, b) => a + b, 0) / n;
    const meanY = ys.reduce((a, b) => a + b, 0) / n;

    let num = 0;
    let denX = 0;
    let denY = 0;

    for (let i = 0; i < n; i++) {
      const dx = xs[i] - meanX;
      const dy = ys[i] - meanY;
      num += dx * dy;
      denX += dx * dx;
      denY += dy * dy;
    }

    const den = Math.sqrt(denX * denY);
    if (den === 0) return 0;
    return Math.round((num / den) * 1000) / 1000;
  }

  // Track Logging into Session Dataset
  function recordTrackToSession(trackMeta, features) {
    if (!trackMeta || !features || !features.tempo) return;
    const trackId = features.id;

    // Avoid duplicate logging if already the most recent entry
    if (sessionTracks.length > 0 && sessionTracks[sessionTracks.length - 1].track_id === trackId) {
      return;
    }

    const keyInfo = formatKeyAndMode(features.key, features.mode);

    const record = {
      timestamp: new Date().toISOString(),
      track_id: trackId,
      track_name: trackMeta.name || "Unknown Track",
      artist: trackMeta.artists?.map((a) => a.name).join(", ") || "Unknown Artist",
      album: trackMeta.album?.name || "Unknown Album",
      duration_ms: trackMeta.duration || 0,
      tempo_bpm: features.tempo,
      key_name: keyInfo.note,
      mode_name: keyInfo.modeStr,
      camelot: keyInfo.camelot,
      energy: features.energy,
      valence: features.valence,
      danceability: features.danceability,
      acousticness: features.acousticness,
      instrumentalness: features.instrumentalness,
      speechiness: features.speechiness,
      liveness: features.liveness,
      loudness_db: features.loudness,
      time_signature: features.time_signature
    };

    sessionTracks.push(record);
    saveSessionTracks();
  }

  // CSV Exporter for R / Python / Excel
  function exportSessionToCSV() {
    if (!sessionTracks || sessionTracks.length === 0) {
      Spicetify.showNotification("No track records in session to export!");
      return;
    }

    const headers = [
      "timestamp",
      "track_id",
      "track_name",
      "artist",
      "album",
      "duration_ms",
      "tempo_bpm",
      "key_name",
      "mode_name",
      "camelot",
      "energy",
      "valence",
      "danceability",
      "acousticness",
      "instrumentalness",
      "speechiness",
      "liveness",
      "loudness_db",
      "time_signature"
    ];

    const escapeCsv = (val) => {
      if (val == null) return "";
      const str = String(val);
      if (str.includes(",") || str.includes('"') || str.includes("\n")) {
        return `"${str.replace(/"/g, '""')}"`;
      }
      return str;
    };

    const rows = sessionTracks.map((row) =>
      headers.map((h) => escapeCsv(row[h])).join(",")
    );

    const csvContent = [headers.join(","), ...rows].join("\r\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);

    const link = document.createElement("a");
    const timestampStr = new Date().toISOString().replace(/[:.]/g, "-");
    link.setAttribute("href", url);
    link.setAttribute("download", `spotify_session_stats_${timestampStr}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);

    Spicetify.showNotification(`Exported ${sessionTracks.length} tracks to CSV!`);
  }

  // HUD Playbar Injection
  function injectHudElement() {
    if (document.getElementById("audiostats-hud-pill")) return;

    // Look for target container in player bar
    const container =
      document.querySelector(".main-nowPlayingBar-left") ||
      document.querySelector("[data-testid='now-playing-widget']") ||
      document.querySelector(".main-nowPlayingWidget-nowPlaying");

    if (!container) return;

    hudElement = document.createElement("button");
    hudElement.id = "audiostats-hud-pill";
    hudElement.title = "Click to open AudioStats & Session Analytics Dashboard";
    hudElement.style.cssText = `
      display: inline-flex;
      align-items: center;
      gap: 6px;
      margin-left: 8px;
      padding: 3px 10px;
      background: rgba(255, 255, 255, 0.08);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 14px;
      font-size: 11px;
      font-weight: 500;
      color: #b3b3b3;
      cursor: pointer;
      transition: all 0.2s ease;
      vertical-align: middle;
      white-space: nowrap;
      user-select: none;
      height: 24px;
    `;

    hudElement.onmouseenter = () => {
      hudElement.style.background = "rgba(255, 255, 255, 0.16)";
      hudElement.style.color = "#ffffff";
      hudElement.style.borderColor = "#1db954";
    };
    hudElement.onmouseleave = () => {
      hudElement.style.background = "rgba(255, 255, 255, 0.08)";
      hudElement.style.color = "#b3b3b3";
      hudElement.style.borderColor = "rgba(255, 255, 255, 0.15)";
    };

    hudElement.onclick = (e) => {
      e.stopPropagation();
      openStatsModal();
    };

    container.appendChild(hudElement);
    updateHudText();
  }

  function updateHudText() {
    if (!hudElement) return;
    if (!currentFeatures) {
      hudElement.innerHTML = `<span>📊 Stats: Loading...</span>`;
      return;
    }

    const keyInfo = formatKeyAndMode(currentFeatures.key, currentFeatures.mode);
    hudElement.innerHTML = `
      <span style="color:#1db954; font-weight:700;">📊</span>
      <span>${currentFeatures.tempo} BPM</span>
      <span style="opacity:0.4;">•</span>
      <span style="color:#64b5f6;">${keyInfo.camelot}</span>
      <span style="opacity:0.4;">•</span>
      <span>V: <b style="color:#a7f3d0;">${currentFeatures.valence}</b></span>
      <span style="opacity:0.4;">•</span>
      <span>E: <b style="color:#fbcfe8;">${currentFeatures.energy}</b></span>
    `;
  }

  // Update on Song Change
  async function handleSongChange() {
    const data = Spicetify.Player.data;
    const track = data?.item;
    if (!track || !track.uri) return;

    // Check if it's a Spotify track URI
    if (!track.uri.startsWith("spotify:track:")) {
      currentTrackId = null;
      currentFeatures = null;
      if (hudElement) {
        hudElement.innerHTML = `<span>📊 Non-Spotify Track</span>`;
      }
      return;
    }

    const trackId = track.uri.split(":")[2];
    currentTrackId = trackId;

    injectHudElement();
    if (hudElement) {
      hudElement.innerHTML = `<span>📊 Loading Stats...</span>`;
    }

    const features = await fetchAudioFeatures(trackId);
    if (features && currentTrackId === trackId) {
      currentFeatures = features;
      updateHudText();
      recordTrackToSession(track, features);
    } else if (hudElement) {
      hudElement.innerHTML = `<span>📊 Stats Unavailable</span>`;
    }
  }

  // Stats Modal UI Builder
  function openStatsModal() {
    const trackData = Spicetify.Player.data?.item;
    const trackName = trackData?.name || "Current Track";
    const artistName = trackData?.artists?.map((a) => a.name).join(", ") || "Artist";

    // Compute Session Statistics
    const bpmList = sessionTracks.map((t) => t.tempo_bpm).filter(Boolean);
    const energyList = sessionTracks.map((t) => t.energy).filter(Boolean);
    const valenceList = sessionTracks.map((t) => t.valence).filter(Boolean);
    const danceList = sessionTracks.map((t) => t.danceability).filter(Boolean);
    const acousticList = sessionTracks.map((t) => t.acousticness).filter(Boolean);

    const bpmStats = calculateSummaryStats(bpmList);
    const energyStats = calculateSummaryStats(energyList);
    const valenceStats = calculateSummaryStats(valenceList);
    const danceStats = calculateSummaryStats(danceList);
    const acousticStats = calculateSummaryStats(acousticList);

    const r_energy_valence = calculatePearsonCorrelation(energyList, valenceList);

    const keyInfo = currentFeatures
      ? formatKeyAndMode(currentFeatures.key, currentFeatures.mode)
      : { note: "N/A", modeStr: "N/A", camelot: "--", full: "N/A" };

    const harmonicKeys = getHarmonicNeighbors(keyInfo.camelot);

    const progressBar = (value, colorHex) => {
      const pct = Math.min(100, Math.max(0, (value || 0) * 100));
      return `
        <div style="background: rgba(255,255,255,0.1); border-radius: 4px; height: 8px; width: 100%; overflow: hidden; position: relative;">
          <div style="background: ${colorHex}; width: ${pct}%; height: 100%; border-radius: 4px; transition: width 0.3s ease;"></div>
        </div>
      `;
    };

    const modalContent = document.createElement("div");
    modalContent.style.cssText = `
      font-family: var(--font-family, sans-serif);
      color: #e0e0e0;
      padding: 10px 5px;
      max-height: 75vh;
      overflow-y: auto;
    `;

    modalContent.innerHTML = `
      <style>
        .as-card {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 10px;
          padding: 14px;
          margin-bottom: 16px;
        }
        .as-metric-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
          gap: 10px;
          margin-top: 10px;
        }
        .as-metric-box {
          background: rgba(0, 0, 0, 0.25);
          border-radius: 8px;
          padding: 10px;
          text-align: center;
          border: 1px solid rgba(255, 255, 255, 0.05);
        }
        .as-metric-val {
          font-size: 18px;
          font-weight: 700;
          color: #ffffff;
          margin-top: 4px;
        }
        .as-metric-lbl {
          font-size: 11px;
          color: #a0a0a0;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .as-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin: 8px 0;
          gap: 12px;
        }
        .as-table {
          width: 100%;
          border-collapse: collapse;
          font-size: 12px;
          margin-top: 8px;
        }
        .as-table th, .as-table td {
          padding: 8px 10px;
          text-align: left;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .as-table th {
          color: #1db954;
          font-weight: 600;
          text-transform: uppercase;
          font-size: 10px;
        }
        .as-btn {
          background: #1db954;
          color: #000000;
          font-weight: 700;
          border: none;
          border-radius: 20px;
          padding: 8px 18px;
          cursor: pointer;
          font-size: 13px;
          transition: transform 0.1s ease, filter 0.2s ease;
        }
        .as-btn:hover {
          filter: brightness(1.15);
          transform: scale(1.02);
        }
        .as-btn-danger {
          background: rgba(239, 68, 68, 0.2);
          color: #f87171;
          border: 1px solid rgba(239, 68, 68, 0.4);
        }
        .as-btn-danger:hover {
          background: rgba(239, 68, 68, 0.3);
          color: #ffffff;
        }
      </style>

      <!-- Track Header -->
      <div style="margin-bottom: 16px;">
        <h2 style="margin: 0; font-size: 20px; color: #ffffff;">📊 ${trackName}</h2>
        <div style="font-size: 13px; color: #a0a0a0; margin-top: 3px;">by ${artistName}</div>
      </div>

      <!-- Current Track Audio Features -->
      <div class="as-card">
        <div style="font-weight: 700; font-size: 14px; color: #ffffff; display: flex; align-items: center; justify-content: space-between;">
          <span>🎧 Current Track Audio Vector</span>
          <span style="font-size: 11px; color: #1db954; font-weight: 600;">Spotify Analysis API</span>
        </div>

        ${
          currentFeatures
            ? `
          <div class="as-metric-grid">
            <div class="as-metric-box">
              <div class="as-metric-lbl">Tempo (BPM)</div>
              <div class="as-metric-val" style="color: #60a5fa;">${currentFeatures.tempo}</div>
            </div>
            <div class="as-metric-box">
              <div class="as-metric-lbl">Key & Scale</div>
              <div class="as-metric-val" style="color: #f472b6;">${keyInfo.note} ${keyInfo.modeStr}</div>
            </div>
            <div class="as-metric-box">
              <div class="as-metric-lbl">Camelot Wheel</div>
              <div class="as-metric-val" style="color: #fbbf24;">${keyInfo.camelot}</div>
            </div>
            <div class="as-metric-box">
              <div class="as-metric-lbl">Loudness (dB)</div>
              <div class="as-metric-val">${currentFeatures.loudness} dB</div>
            </div>
          </div>

          <div style="margin-top: 14px;">
            <div class="as-row">
              <span style="font-size: 12px; min-width: 130px;">Energy (Intensity)</span>
              ${progressBar(currentFeatures.energy, "#f43f5e")}
              <span style="font-size: 12px; font-weight: 600; min-width: 40px; text-align: right;">${currentFeatures.energy}</span>
            </div>
            <div class="as-row">
              <span style="font-size: 12px; min-width: 130px;">Valence (Positivity)</span>
              ${progressBar(currentFeatures.valence, "#10b981")}
              <span style="font-size: 12px; font-weight: 600; min-width: 40px; text-align: right;">${currentFeatures.valence}</span>
            </div>
            <div class="as-row">
              <span style="font-size: 12px; min-width: 130px;">Danceability</span>
              ${progressBar(currentFeatures.danceability, "#8b5cf6")}
              <span style="font-size: 12px; font-weight: 600; min-width: 40px; text-align: right;">${currentFeatures.danceability}</span>
            </div>
            <div class="as-row">
              <span style="font-size: 12px; min-width: 130px;">Acousticness</span>
              ${progressBar(currentFeatures.acousticness, "#38bdf8")}
              <span style="font-size: 12px; font-weight: 600; min-width: 40px; text-align: right;">${currentFeatures.acousticness}</span>
            </div>
            <div class="as-row">
              <span style="font-size: 12px; min-width: 130px;">Instrumentalness</span>
              ${progressBar(currentFeatures.instrumentalness, "#eab308")}
              <span style="font-size: 12px; font-weight: 600; min-width: 40px; text-align: right;">${currentFeatures.instrumentalness}</span>
            </div>
            <div class="as-row">
              <span style="font-size: 12px; min-width: 130px;">Speechiness</span>
              ${progressBar(currentFeatures.speechiness, "#a855f7")}
              <span style="font-size: 12px; font-weight: 600; min-width: 40px; text-align: right;">${currentFeatures.speechiness}</span>
            </div>
          </div>

          <!-- Harmonic Mixing Compatibility -->
          <div style="margin-top: 14px; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.08);">
            <div style="font-size: 11px; text-transform: uppercase; color: #a0a0a0; margin-bottom: 6px; font-weight: 600;">
              Harmonic Mixing Match Candidates
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
              ${harmonicKeys
                .map(
                  (h) => `
                <div style="background: rgba(255,255,255,0.06); padding: 4px 10px; border-radius: 6px; font-size: 12px; border: 1px solid rgba(255,255,255,0.08);">
                  <strong style="color: #60a5fa;">${h.code}</strong> <span style="font-size: 10px; color: #9ca3af;">(${h.type})</span>
                </div>
              `
                )
                .join("")}
            </div>
          </div>
        `
            : `
          <div style="text-align: center; padding: 20px; color: #888888;">
            No audio feature vector available for the current item.
          </div>
        `
        }
      </div>

      <!-- Session Statistical Distribution -->
      <div class="as-card">
        <div style="font-weight: 700; font-size: 14px; color: #ffffff; display: flex; align-items: center; justify-content: space-between;">
          <span>📈 Session Sample Statistics (n = ${sessionTracks.length} tracks)</span>
          <span style="font-size: 11px; color: #60a5fa;">Descriptive Estimators</span>
        </div>

        ${
          sessionTracks.length > 0
            ? `
          <table class="as-table">
            <thead>
              <tr>
                <th>Variable (X)</th>
                <th>Mean (μ̄)</th>
                <th>Std Dev (s)</th>
                <th>Min</th>
                <th>Max</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Tempo (BPM)</strong></td>
                <td>${bpmStats.mean}</td>
                <td>${bpmStats.std}</td>
                <td>${bpmStats.min}</td>
                <td>${bpmStats.max}</td>
              </tr>
              <tr>
                <td><strong>Energy</strong></td>
                <td>${energyStats.mean}</td>
                <td>${energyStats.std}</td>
                <td>${energyStats.min}</td>
                <td>${energyStats.max}</td>
              </tr>
              <tr>
                <td><strong>Valence (Mood)</strong></td>
                <td>${valenceStats.mean}</td>
                <td>${valenceStats.std}</td>
                <td>${valenceStats.min}</td>
                <td>${valenceStats.max}</td>
              </tr>
              <tr>
                <td><strong>Danceability</strong></td>
                <td>${danceStats.mean}</td>
                <td>${danceStats.std}</td>
                <td>${danceStats.min}</td>
                <td>${danceStats.max}</td>
              </tr>
              <tr>
                <td><strong>Acousticness</strong></td>
                <td>${acousticStats.mean}</td>
                <td>${acousticStats.std}</td>
                <td>${acousticStats.min}</td>
                <td>${acousticStats.max}</td>
              </tr>
            </tbody>
          </table>

          <!-- Bivariate Correlation -->
          <div style="margin-top: 14px; padding: 10px; background: rgba(0,0,0,0.3); border-radius: 8px; border-left: 3px solid #1db954;">
            <div style="font-size: 12px; font-weight: 600; color: #ffffff;">
              Pearson Correlation: r(Energy, Valence) = <span style="color: #1db954; font-size: 14px;">${
                r_energy_valence != null ? r_energy_valence : "N/A (need n ≥ 2)"
              }</span>
            </div>
            <div style="font-size: 11px; color: #9ca3af; margin-top: 4px;">
              ${
                r_energy_valence != null
                  ? Math.abs(r_energy_valence) > 0.5
                    ? "Strong linear relationship between musical arousal/energy and positive affect."
                    : Math.abs(r_energy_valence) > 0.25
                    ? "Moderate correlation between energy and musical mood."
                    : "Low linear correlation: energetic tracks vary widely between minor and major emotions."
                  : "Collect at least 2 tracks in your current session to calculate bivariate correlation."
              }
            </div>
          </div>
        `
            : `
          <div style="text-align: center; padding: 15px; color: #888888; font-size: 12px;">
            Start playing songs to aggregate statistical sample distributions!
          </div>
        `
        }
      </div>

      <!-- Controls & Actions -->
      <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
        <button id="as-btn-export" class="as-btn">
          📥 Export Sample to CSV (R / Python)
        </button>
        <button id="as-btn-reset" class="as-btn as-btn-danger">
          🔄 Reset Session Sample
        </button>
      </div>
    `;

    // Bind Modal Action Buttons
    const exportBtn = modalContent.querySelector("#as-btn-export");
    if (exportBtn) {
      exportBtn.onclick = () => exportSessionToCSV();
    }

    const resetBtn = modalContent.querySelector("#as-btn-reset");
    if (resetBtn) {
      resetBtn.onclick = () => {
        if (confirm("Reset current session dataset? This will clear all recorded sample tracks.")) {
          sessionTracks = [];
          saveSessionTracks();
          Spicetify.showNotification("Session sample reset!");
          Spicetify.PopupModal.hide();
        }
      };
    }

    Spicetify.PopupModal.display({
      title: "AudioStats & Session Analytics",
      content: modalContent,
      isLarge: true
    });
  }

  // Add Topbar Icon Button
  function setupTopbarButton() {
    new Spicetify.Topbar.Button(
      "AudioStats",
      `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="18" y1="20" x2="18" y2="10"></line>
        <line x1="12" y1="20" x2="12" y2="4"></line>
        <line x1="6" y1="20" x2="6" y2="14"></line>
      </svg>
      `,
      () => openStatsModal()
    );
  }

  // Periodic Observer to keep HUD pill in playbar if Spotify re-renders DOM
  function setupDomWatcher() {
    setInterval(() => {
      if (!document.getElementById("audiostats-hud-pill") && Spicetify.Player.data?.item) {
        injectHudElement();
        updateHudText();
      }
    }, 2000);
  }

  // Extension Initialization
  function init() {
    console.log(`[${SCRIPT_NAME}] Initializing extension...`);
    setupTopbarButton();
    setupDomWatcher();

    Spicetify.Player.addEventListener("songchange", handleSongChange);

    // Initial check for currently playing track
    if (Spicetify.Player.data?.item) {
      handleSongChange();
    }

    console.log(`[${SCRIPT_NAME}] Loaded successfully.`);
  }

  init();
})();
