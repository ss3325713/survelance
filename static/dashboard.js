/**
 * PySURVEILLANCE — Security Operations Center (SOC) Console v2.0
 * Complete Functionality Integration & Control Controller
 *
 * Fully wires all 10 SPA views, hardware controls, flashlight automation,
 * real-time SSE streaming, dual-mode video monitors, incident forensic comparison,
 * and cryptographic security sessions.
 */

(function () {
  'use strict';

  // Master Application State
  const state = {
    currentView: 'overview',
    isAuthenticated: false,
    sessionToken: localStorage.getItem('pysurv_session_token') || '',
    csrfToken: '',
    streamMode: 'mjpeg', // 'mjpeg' | 'canvas'
    canvasTimer: null,
    statusPollTimer: null,
    eventsPollTimer: null,
    storagePollTimer: null,
    eventSource: null,
    events: [],
    selectedCategory: 'all',
    searchQuery: '',
    incidentViewMode: 'timeline', // 'timeline' | 'gallery'
    lastStatus: null,
    isSurveillanceArmed: true,
    cameraSettings: {
      quality: 95,
      exposure: -2,
      gamma: 0.75,
      brightness: -15,
      contrast: 1.15,
      white_balance: 'auto',
      auto_hdr: false,
      night_vision: false,
      torch: false,
      resolution: '1280x720'
    },
    activeEventData: null
  };

  // DOM Elements Cache
  const DOM = {};

  function cacheDom() {
    // Navigation & Views
    DOM.sidebar = document.getElementById('socSidebar');
    DOM.sidebarCollapseBtn = document.getElementById('sidebarCollapseBtn');
    DOM.mobileMenuBtn = document.getElementById('mobileMenuBtn');
    DOM.currentViewTitle = document.getElementById('currentViewTitle');
    DOM.views = document.querySelectorAll('.soc-view');
    DOM.navItems = document.querySelectorAll('.nav-item');
    DOM.sidebarLiveTag = document.getElementById('sidebarLiveTag');
    DOM.sidebarIncidentCount = document.getElementById('sidebarIncidentCount');
    DOM.sidebarAudioDot = document.getElementById('sidebarAudioDot');
    DOM.sidebarPushStatusTag = document.getElementById('sidebarPushStatusTag');
    DOM.sidebarHostStatus = document.getElementById('sidebarHostStatus');
    DOM.sidebarPinBtn = document.getElementById('sidebarPinBtn');
    DOM.sidebarPinText = document.getElementById('sidebarPinText');

    // Topbar Controls
    DOM.masterSurveillanceBtn = document.getElementById('masterSurveillanceBtn');
    DOM.masterSurveillanceLabel = document.getElementById('masterSurveillanceLabel');
    DOM.btnNightDay = document.getElementById('btnNightDay');
    DOM.btnNightNight = document.getElementById('btnNightNight');
    DOM.btnNightAuto = document.getElementById('btnNightAuto');
    DOM.uptimeText = document.getElementById('uptimeText');
    DOM.cameraPill = document.getElementById('cameraPill');
    DOM.cameraPillText = document.getElementById('cameraPillText');
    DOM.micPill = document.getElementById('micPill');
    DOM.micPillText = document.getElementById('micPillText');
    DOM.dbPill = document.getElementById('dbPill');
    DOM.dbStatusText = document.getElementById('dbStatusText');
    DOM.togglePushNavBtn = document.getElementById('togglePushNavBtn');
    DOM.qrBtn = document.getElementById('qrBtn');
    DOM.testAlarmBtn = document.getElementById('testAlarmBtn');
    DOM.fullscreenBtn = document.getElementById('fullscreenBtn');

    // Overview View
    DOM.overviewRefreshBtn = document.getElementById('overviewRefreshBtn');
    DOM.todayEventsCount = document.getElementById('todayEventsCount');
    DOM.todayIncidentsBadge = document.getElementById('todayIncidentsBadge');
    DOM.lastDetectionTimeText = document.getElementById('lastDetectionTimeText');
    DOM.overviewCamBadge = document.getElementById('overviewCamBadge');
    DOM.overviewFpsValue = document.getElementById('overviewFpsValue');
    DOM.overviewCamMeta = document.getElementById('overviewCamMeta');
    DOM.overviewMicBadge = document.getElementById('overviewMicBadge');
    DOM.overviewMicRms = document.getElementById('overviewMicRms');
    DOM.overviewFlashBadge = document.getElementById('overviewFlashBadge');
    DOM.overviewFlashTrigger = document.getElementById('overviewFlashTrigger');
    DOM.overviewTorchAutoBtn = document.getElementById('overviewTorchAutoBtn');
    DOM.overviewTorchOnBtn = document.getElementById('overviewTorchOnBtn');
    DOM.overviewTorchOffBtn = document.getElementById('overviewTorchOffBtn');
    DOM.overviewStreamImg = document.getElementById('overviewStreamImg');
    DOM.overviewHudFps = document.getElementById('overviewHudFps');
    DOM.overviewHudRes = document.getElementById('overviewHudRes');
    DOM.overviewStartBtn = document.getElementById('overviewStartBtn');
    DOM.overviewStopBtn = document.getElementById('overviewStopBtn');
    DOM.overviewTorchBtn = document.getElementById('overviewTorchBtn');
    DOM.overviewSnapshotBtn = document.getElementById('overviewSnapshotBtn');
    DOM.overviewTestPushBtn = document.getElementById('overviewTestPushBtn');
    DOM.latestEventImg = document.getElementById('latestEventImg');
    DOM.latestEventTagBadge = document.getElementById('latestEventTagBadge');
    DOM.latestEventLabelText = document.getElementById('latestEventLabelText');
    DOM.latestEventConfidence = document.getElementById('latestEventConfidence');
    DOM.latestEventTimeBadge = document.getElementById('latestEventTimeBadge');
    DOM.latestEventAgeText = document.getElementById('latestEventAgeText');
    DOM.latestEventCategoryBadge = document.getElementById('latestEventCategoryBadge');
    DOM.viewLatestEventBtn = document.getElementById('viewLatestEventBtn');

    // Live Monitoring View
    DOM.cinemaScreen = document.getElementById('cinemaScreen');
    DOM.liveStreamImg = document.getElementById('liveStreamImg');
    DOM.liveCanvas = document.getElementById('liveCanvas');
    DOM.hudModeBadge = document.getElementById('hudModeBadge');
    DOM.telemetryFps = document.getElementById('telemetryFps');
    DOM.telemetryProcFps = document.getElementById('telemetryProcFps');
    DOM.telemetryLatency = document.getElementById('telemetryLatency');
    DOM.liveResBadge = document.getElementById('liveResBadge');
    DOM.cameraDisconnectBanner = document.getElementById('cameraDisconnectBanner');
    DOM.bannerRetryCamBtn = document.getElementById('bannerRetryCamBtn');
    DOM.modeMjpegBtn = document.getElementById('modeMjpegBtn');
    DOM.modeCanvasBtn = document.getElementById('modeCanvasBtn');
    DOM.modeDirectPhoneLink = document.getElementById('modeDirectPhoneLink');
    DOM.hudTorchBtn = document.getElementById('hudTorchBtn');
    DOM.fastRefreshBtn = document.getElementById('fastRefreshBtn');
    DOM.snapshotBtn = document.getElementById('snapshotBtn');
    DOM.toggleCinemaFullscreenBtn = document.getElementById('toggleCinemaFullscreenBtn');

    // Camera Hardware Console
    DOM.selectResolution = document.getElementById('selectResolution');
    DOM.selectResolutionVal = document.getElementById('selectResolutionVal');
    DOM.sliderQuality = document.getElementById('sliderQuality');
    DOM.sliderQualityVal = document.getElementById('sliderQualityVal');
    DOM.sliderExposure = document.getElementById('sliderExposure');
    DOM.sliderExposureVal = document.getElementById('sliderExposureVal');
    DOM.sliderGamma = document.getElementById('sliderGamma');
    DOM.sliderGammaVal = document.getElementById('sliderGammaVal');
    DOM.sliderBrightness = document.getElementById('sliderBrightness');
    DOM.sliderBrightnessVal = document.getElementById('sliderBrightnessVal');
    DOM.sliderContrast = document.getElementById('sliderContrast');
    DOM.sliderContrastVal = document.getElementById('sliderContrastVal');
    DOM.selectWhiteBalance = document.getElementById('selectWhiteBalance');
    DOM.toggleHdrBtn = document.getElementById('toggleHdrBtn');
    DOM.toggleTorchBtn = document.getElementById('toggleTorchBtn');
    DOM.toggleNightBtn = document.getElementById('toggleNightBtn');
    DOM.testCamBtn = document.getElementById('testCamBtn');
    DOM.camToggleSurveillanceBtn = document.getElementById('camToggleSurveillanceBtn');
    DOM.camFastRefreshBtn = document.getElementById('camFastRefreshBtn');
    DOM.resetControlsBtn = document.getElementById('resetControlsBtn');

    // Detection Center
    DOM.detActiveProfile = document.getElementById('detActiveProfile');
    DOM.detMinArea = document.getElementById('detMinArea');
    DOM.detMotionThresh = document.getElementById('detMotionThresh');
    DOM.detMeasuredLux = document.getElementById('detMeasuredLux');
    DOM.detConfidenceDisplay = document.getElementById('detConfidenceDisplay');
    DOM.detThresholdSlider = document.getElementById('detThresholdSlider');
    DOM.detThresholdVal = document.getElementById('detThresholdVal');
    DOM.detConfidenceSlider = document.getElementById('detConfidenceSlider');
    DOM.detConfidenceVal = document.getElementById('detConfidenceVal');
    DOM.detSaveSettingsBtn = document.getElementById('detSaveSettingsBtn');

    // Incident History
    DOM.incidentSearchInput = document.getElementById('incidentSearchInput');
    DOM.viewTabTimeline = document.getElementById('viewTabTimeline');
    DOM.viewTabGallery = document.getElementById('viewTabGallery');
    DOM.clearEventsBtn = document.getElementById('clearEventsBtn');
    DOM.eventsList = document.getElementById('eventsList');
    DOM.catPills = document.querySelectorAll('.cat-pill');
    DOM.countAll = document.getElementById('countAll');
    DOM.countPerson = document.getElementById('countPerson');
    DOM.countBird = document.getElementById('countBird');
    DOM.countAnimal = document.getElementById('countAnimal');
    DOM.countMonkey = document.getElementById('countMonkey');
    DOM.countMotion = document.getElementById('countMotion');

    // Notifications Center
    DOM.notifTestPushBtn = document.getElementById('notifTestPushBtn');
    DOM.notifTestAlarmBtn = document.getElementById('notifTestAlarmBtn');
    DOM.notifSseStatusBadge = document.getElementById('notifSseStatusBadge');
    DOM.notifPushEnabled = document.getElementById('notifPushEnabled');
    DOM.notifSoundAlarmEnabled = document.getElementById('notifSoundAlarmEnabled');
    DOM.notifReqPermBtn = document.getElementById('notifReqPermBtn');
    DOM.notifCdPerson = document.getElementById('notifCdPerson');
    DOM.notifCdAnimal = document.getElementById('notifCdAnimal');
    DOM.notifCdMotion = document.getElementById('notifCdMotion');
    DOM.notifEventTableBody = document.getElementById('notifEventTableBody');

    // Phone Audio Monitoring
    DOM.testAudioBtn = document.getElementById('testAudioBtn');
    DOM.audioStateBadge = document.getElementById('audioStateBadge');
    DOM.audioMeterFill = document.getElementById('audioMeterFill');
    DOM.audioRmsText = document.getElementById('audioRmsText');
    DOM.audioNoiseFloorText = document.getElementById('audioNoiseFloorText');
    DOM.audioSnrText = document.getElementById('audioSnrText');
    DOM.audioFormatText = document.getElementById('audioFormatText');
    DOM.audioStreamUrlText = document.getElementById('audioStreamUrlText');

    // Flashlight Automation
    DOM.flashlightStatusPill = document.getElementById('flashlightStatusPill');
    DOM.flashlightLightingText = document.getElementById('flashlightLightingText');
    DOM.btnFlashlightAuto = document.getElementById('btnFlashlightAuto');
    DOM.btnFlashlightManual = document.getElementById('btnFlashlightManual');
    DOM.btnFlashlightOff = document.getElementById('btnFlashlightOff');
    DOM.flashlightCountdownText = document.getElementById('flashlightCountdownText');
    DOM.flashlightCountdownFill = document.getElementById('flashlightCountdownFill');
    DOM.flashlightMotionText = document.getElementById('flashlightMotionText');
    DOM.flashlightTriggerText = document.getElementById('flashlightTriggerText');
    DOM.flashlightRequestedText = document.getElementById('flashlightRequestedText');
    DOM.flashlightResultText = document.getElementById('flashlightResultText');
    DOM.flashlightLogTableBody = document.getElementById('flashlightLogTableBody');

    // System Analytics
    DOM.analyticsBackupBtn = document.getElementById('analyticsBackupBtn');
    DOM.analyticsPurgeBtn = document.getElementById('analyticsPurgeBtn');
    DOM.metricCpu = document.getElementById('metricCpu');
    DOM.metricCpuBar = document.getElementById('metricCpuBar');
    DOM.metricRam = document.getElementById('metricRam');
    DOM.metricRamBar = document.getElementById('metricRamBar');
    DOM.metricRamMb = document.getElementById('metricRamMb');
    DOM.throttleStatus = document.getElementById('throttleStatus');
    DOM.analyticsDbRows = document.getElementById('analyticsDbRows');
    DOM.storageImageCount = document.getElementById('storageImageCount');
    DOM.storageUsedMbText = document.getElementById('storageUsedMbText');
    DOM.storageBar = document.getElementById('storageBar');
    DOM.storagePercentBadge = document.getElementById('storagePercentBadge');

    // Security & Access
    DOM.securityLogoutBtn = document.getElementById('securityLogoutBtn');

    // Settings
    DOM.saveGlobalSettingsBtn = document.getElementById('saveGlobalSettingsBtn');
    DOM.cfgPhoneIp = document.getElementById('cfgPhoneIp');
    DOM.cfgPhonePort = document.getElementById('cfgPhonePort');
    DOM.cfgVideoEp = document.getElementById('cfgVideoEp');
    DOM.cfgSnapshotEp = document.getElementById('cfgSnapshotEp');
    DOM.cfgAudioEp = document.getElementById('cfgAudioEp');
    DOM.cfgMotionFps = document.getElementById('cfgMotionFps');
    DOM.cfgAiFps = document.getElementById('cfgAiFps');
    DOM.cfgMotionThresh = document.getElementById('cfgMotionThresh');
    DOM.cfgConfidence = document.getElementById('cfgConfidence');
    DOM.cfgAutoThrottle = document.getElementById('cfgAutoThrottle');
    DOM.cfgSoundEnabled = document.getElementById('cfgSoundEnabled');
    DOM.cfgCdPerson = document.getElementById('cfgCdPerson');
    DOM.cfgCdAnimal = document.getElementById('cfgCdAnimal');
    DOM.cfgCdMotion = document.getElementById('cfgCdMotion');
    DOM.cfgFlashTimeout = document.getElementById('cfgFlashTimeout');
    DOM.cfgFlashLuxCutoff = document.getElementById('cfgFlashLuxCutoff');
    DOM.cfgRetentionDays = document.getElementById('cfgRetentionDays');
    DOM.cfgStorageLimitMb = document.getElementById('cfgStorageLimitMb');
    DOM.cfgNewPin = document.getElementById('cfgNewPin');

    // Modals
    DOM.qrModal = document.getElementById('qrModal');
    DOM.qrCodeContainer = document.getElementById('qrCodeContainer');
    DOM.phoneUrlText = document.getElementById('phoneUrlText');
    DOM.phoneUrlLink = document.getElementById('phoneUrlLink');
    DOM.copyUrlBtn = document.getElementById('copyUrlBtn');

    DOM.pinModal = document.getElementById('pinModal');
    DOM.pinForm = document.getElementById('pinForm');
    DOM.pinInput = document.getElementById('pinInput');
    DOM.pinError = document.getElementById('pinError');

    DOM.eventDetailModal = document.getElementById('eventDetailModal');
    DOM.eventDetailTitle = document.getElementById('eventDetailTitle');
    DOM.comparisonTabBar = document.getElementById('comparisonTabBar');
    DOM.btnCompInitial = document.getElementById('btnCompInitial');
    DOM.btnCompFinal = document.getElementById('btnCompFinal');
    DOM.btnCompSideBySide = document.getElementById('btnCompSideBySide');
    DOM.singleImgContainer = document.getElementById('singleImgContainer');
    DOM.eventDetailImg = document.getElementById('eventDetailImg');
    DOM.sideBySideContainer = document.getElementById('sideBySideContainer');
    DOM.eventDetailInitialImg = document.getElementById('eventDetailInitialImg');
    DOM.eventDetailFinalImg = document.getElementById('eventDetailFinalImg');
    DOM.eventDetailCategory = document.getElementById('eventDetailCategory');
    DOM.eventDetailTimestamp = document.getElementById('eventDetailTimestamp');
    DOM.eventDetailConfidence = document.getElementById('eventDetailConfidence');
    DOM.eventDetailLabel = document.getElementById('eventDetailLabel');
    DOM.eventDetailJson = document.getElementById('eventDetailJson');
    DOM.downloadEventImgBtn = document.getElementById('downloadEventImgBtn');
    DOM.deleteEventBtn = document.getElementById('deleteEventBtn');

    DOM.toastContainer = document.getElementById('toastContainer');
    DOM.pushBannerContainer = document.getElementById('pushBannerContainer');
  }

  // =========================================================================
  // API Fetch Helper with Session & Cookie Support
  // =========================================================================
  async function apiFetch(endpoint, options = {}) {
    const headers = options.headers || {};
    if (state.sessionToken) {
      headers['X-Dashboard-Token'] = state.sessionToken;
      headers['X-Session-Token'] = state.sessionToken;
    }
    if (state.csrfToken) {
      headers['X-CSRF-Token'] = state.csrfToken;
    }
    if (options.body && typeof options.body === 'object' && !(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.body);
    }
    options.headers = headers;
    options.credentials = 'same-origin';

    try {
      const response = await fetch(endpoint, options);
      if (response.status === 401) {
        state.isAuthenticated = false;
        updateAuthUI();
        if (options.method && options.method !== 'GET') {
          openPinModal();
        }
      } else if (response.ok && state.sessionToken) {
        state.isAuthenticated = true;
        updateAuthUI();
      }
      return response;
    } catch (err) {
      console.warn(`API Error [${endpoint}]:`, err);
      throw err;
    }
  }

  // =========================================================================
  // Toast & Notifications
  // =========================================================================
  function showToast(message, type = 'info', duration = 3500) {
    if (!DOM.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `soc-toast toast-${type}`;
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'warning') icon = '⚠️';
    if (type === 'danger') icon = '🚨';

    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    DOM.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.25s ease';
      setTimeout(() => toast.remove(), 250);
    }, duration);
  }

  function showPushBanner(eventData) {
    if (!DOM.pushBannerContainer) return;
    const card = document.createElement('div');
    card.className = 'push-card';
    card.innerHTML = `
      <div style="font-size: 1.4rem;">🚨</div>
      <div>
        <div style="font-weight: 700; color: #ffffff; font-size: 0.85rem;">${eventData.title || eventData.category || 'Surveillance Event'}</div>
        <div style="font-size: 0.75rem; color: #94a3b8;">${eventData.body || eventData.label || 'Motion detected in monitored zone'}</div>
      </div>
    `;
    card.onclick = () => {
      navigateToView('incidents');
      card.remove();
    };
    DOM.pushBannerContainer.appendChild(card);
    setTimeout(() => {
      card.style.opacity = '0';
      card.style.transition = 'opacity 0.3s ease';
      setTimeout(() => card.remove(), 300);
    }, 6000);

    // Also append to Notifications table
    appendNotificationLog(eventData);
  }

  function appendNotificationLog(item) {
    if (!DOM.notifEventTableBody) return;
    const tr = document.createElement('tr');
    const timeStr = new Date().toLocaleTimeString();
    const type = item.type || item.category || 'Alert';
    const msg = item.body || item.label || item.message || JSON.stringify(item);
    tr.innerHTML = `
      <td style="font-family: monospace;">${timeStr}</td>
      <td><span class="badge ${getCategoryBadgeClass(type)}">${type}</span></td>
      <td>${msg}</td>
    `;
    if (DOM.notifEventTableBody.querySelector('td[colspan]')) {
      DOM.notifEventTableBody.innerHTML = '';
    }
    DOM.notifEventTableBody.insertBefore(tr, DOM.notifEventTableBody.firstChild);
  }

  // =========================================================================
  // SPA Routing & Navigation
  // =========================================================================
  function handleHashChange() {
    let hash = window.location.hash.replace('#', '').trim();
    if (!hash) hash = 'overview';
    navigateToView(hash);
  }

  function navigateToView(viewName) {
    state.currentView = viewName;
    let found = false;

    DOM.views.forEach(view => {
      if (view.id === `view-${viewName}`) {
        view.classList.add('active');
        found = true;
      } else {
        view.classList.remove('active');
      }
    });

    if (!found && DOM.views.length > 0) {
      DOM.views[0].classList.add('active');
      state.currentView = 'overview';
    }

    DOM.navItems.forEach(item => {
      if (item.getAttribute('data-view') === state.currentView) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    const titles = {
      overview: 'Command & Overview',
      monitoring: 'Live Monitoring Console',
      detection: 'Detection & Classification',
      incidents: 'Incident History & Gallery',
      notifications: 'Notifications & Deterrence',
      audio: 'Phone Audio Monitoring',
      automation: 'Flashlight Automation',
      analytics: 'System Analytics',
      security: 'Security & Access Control',
      settings: 'System Configuration'
    };
    if (DOM.currentViewTitle) {
      DOM.currentViewTitle.textContent = titles[state.currentView] || 'PySURVEILLANCE SOC';
    }

    // Close mobile menu if open
    if (DOM.sidebar) {
      DOM.sidebar.classList.remove('mobile-open');
    }

    // Lazy load or refresh view-specific data
    if (state.currentView === 'incidents') {
      fetchEvents();
    } else if (state.currentView === 'notifications') {
      fetchPushStatus();
    } else if (state.currentView === 'analytics') {
      fetchStorageStats();
    } else if (state.currentView === 'settings') {
      loadConfigSettings();
    } else if (state.currentView === 'monitoring') {
      loadCameraControls();
    }
  }

  // =========================================================================
  // Stream Management (MJPEG & Canvas Safe)
  // =========================================================================
  function initStreamPlayers() {
    setStreamMode('mjpeg');

    if (DOM.modeMjpegBtn) {
      DOM.modeMjpegBtn.addEventListener('click', () => setStreamMode('mjpeg'));
    }
    if (DOM.modeCanvasBtn) {
      DOM.modeCanvasBtn.addEventListener('click', () => setStreamMode('canvas'));
    }

    // Fast Refresh button
    const doFastRefresh = () => {
      showToast('Refreshing camera stream...', 'info', 1500);
      if (state.streamMode === 'mjpeg') {
        if (DOM.liveStreamImg) DOM.liveStreamImg.src = `/api/stream/live?t=${Date.now()}`;
        if (DOM.overviewStreamImg) DOM.overviewStreamImg.src = `/api/stream/live?t=${Date.now()}`;
      } else {
        startCanvasStream();
      }
    };
    if (DOM.fastRefreshBtn) DOM.fastRefreshBtn.addEventListener('click', doFastRefresh);
    if (DOM.camFastRefreshBtn) DOM.camFastRefreshBtn.addEventListener('click', doFastRefresh);

    // Snapshot button actions
    const triggerSnapshot = async () => {
      try {
        const res = await apiFetch('/api/stream/snapshot');
        if (res.ok) {
          const blob = await res.blob();
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = `snapshot_${Date.now()}.jpg`;
          a.click();
          URL.revokeObjectURL(url);
          showToast('Snapshot downloaded successfully', 'success');
        }
      } catch (err) {
        showToast('Failed to capture snapshot', 'danger');
      }
    };

    if (DOM.snapshotBtn) DOM.snapshotBtn.addEventListener('click', triggerSnapshot);
    if (DOM.overviewSnapshotBtn) DOM.overviewSnapshotBtn.addEventListener('click', triggerSnapshot);

    // Fullscreen monitor actions
    const toggleFullscreen = () => {
      if (!document.fullscreenElement) {
        const target = DOM.cinemaScreen || document.documentElement;
        target.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    };
    if (DOM.toggleCinemaFullscreenBtn) DOM.toggleCinemaFullscreenBtn.addEventListener('click', toggleFullscreen);
    if (DOM.fullscreenBtn) DOM.fullscreenBtn.addEventListener('click', toggleFullscreen);

    if (DOM.bannerRetryCamBtn) {
      DOM.bannerRetryCamBtn.addEventListener('click', async () => {
        showToast('Initiating camera reconnection...', 'info');
        await apiFetch('/api/camera/reconnect', { method: 'POST' });
        setStreamMode(state.streamMode);
      });
    }
  }

  function setStreamMode(mode) {
    state.streamMode = mode;
    if (DOM.modeMjpegBtn) DOM.modeMjpegBtn.classList.toggle('active', mode === 'mjpeg');
    if (DOM.modeCanvasBtn) DOM.modeCanvasBtn.classList.toggle('active', mode === 'canvas');

    if (mode === 'mjpeg') {
      if (state.canvasTimer) {
        clearInterval(state.canvasTimer);
        state.canvasTimer = null;
      }
      if (DOM.liveCanvas) DOM.liveCanvas.style.display = 'none';
      if (DOM.liveStreamImg) {
        DOM.liveStreamImg.style.display = 'block';
        DOM.liveStreamImg.src = `/api/stream/live?t=${Date.now()}`;
      }
      if (DOM.overviewStreamImg) {
        DOM.overviewStreamImg.src = `/api/stream/live?t=${Date.now()}`;
      }
    } else if (mode === 'canvas') {
      if (DOM.liveStreamImg) {
        DOM.liveStreamImg.src = '';
        DOM.liveStreamImg.style.display = 'none';
      }
      if (DOM.liveCanvas) DOM.liveCanvas.style.display = 'block';
      startCanvasStream();
    }
  }

  function startCanvasStream() {
    if (state.canvasTimer) clearInterval(state.canvasTimer);
    const canvas = DOM.liveCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const img = new Image();

    img.onload = () => {
      canvas.width = img.naturalWidth || 1280;
      canvas.height = img.naturalHeight || 720;
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    };

    const fetchFrame = () => {
      if (state.streamMode !== 'canvas') return;
      img.src = `/api/stream/snapshot?t=${Date.now()}`;
    };

    fetchFrame();
    state.canvasTimer = setInterval(fetchFrame, 250); // 4 FPS safe poll
  }

  // =========================================================================
  // Telemetry Poller & UI Synchronizer
  // =========================================================================
  async function pollStatus() {
    try {
      const res = await apiFetch('/api/status');
      if (!res.ok) return;
      const data = await res.json();
      state.lastStatus = data;
      renderStatus(data);
    } catch (err) {
      console.warn('Status poll error:', err);
    }
  }

  function renderStatus(s) {
    if (!s) return;

    const monitoring = s.monitoring || {};
    const cam = s.camera || {};
    const audio = s.microphone || s.audio || {};
    const flash = s.flashlight || {};
    const metrics = s.metrics || s.system || {};
    const night = s.night_mode || {};

    // Master armed state
    state.isSurveillanceArmed = (s.surveillance_enabled !== undefined)
      ? !!s.surveillance_enabled
      : (monitoring.is_monitoring !== undefined ? !!monitoring.is_monitoring : true);

    if (DOM.masterSurveillanceBtn) {
      DOM.masterSurveillanceBtn.classList.toggle('active', state.isSurveillanceArmed);
      DOM.masterSurveillanceBtn.classList.toggle('disarmed', !state.isSurveillanceArmed);
    }
    if (DOM.masterSurveillanceLabel) {
      DOM.masterSurveillanceLabel.textContent = state.isSurveillanceArmed ? 'SURVEILLANCE: ARMED' : 'SURVEILLANCE: DISARMED';
    }
    if (DOM.camToggleSurveillanceBtn) {
      DOM.camToggleSurveillanceBtn.textContent = state.isSurveillanceArmed ? '🛡️ Surveillance: ARMED' : '🛡️ Surveillance: DISARMED';
      DOM.camToggleSurveillanceBtn.classList.toggle('btn-primary', state.isSurveillanceArmed);
    }

    // Uptime
    if (DOM.uptimeText) {
      if (monitoring.monitoring_uptime_str) {
        DOM.uptimeText.textContent = monitoring.monitoring_uptime_str;
      } else if (s.uptime_seconds !== undefined) {
        const hrs = Math.floor(s.uptime_seconds / 3600);
        const mins = Math.floor((s.uptime_seconds % 3600) / 60);
        const secs = s.uptime_seconds % 60;
        DOM.uptimeText.textContent = `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      }
    }

    // Camera Subsystem
    const camOk = cam.is_online !== undefined ? !!cam.is_online : !!s.camera_connected;
    if (DOM.cameraPill) {
      DOM.cameraPill.className = `soc-pill ${camOk ? 'pill-success' : 'pill-danger'}`;
    }
    if (DOM.cameraPillText) {
      DOM.cameraPillText.textContent = camOk ? 'CAM: CONNECTED' : 'CAM: DISCONNECTED';
    }
    if (DOM.overviewCamBadge) {
      DOM.overviewCamBadge.className = `stat-badge ${camOk ? 'badge-success' : 'badge-danger'}`;
      DOM.overviewCamBadge.textContent = camOk ? 'ONLINE' : 'DISCONNECTED';
    }
    if (DOM.cameraDisconnectBanner) {
      DOM.cameraDisconnectBanner.style.display = camOk ? 'none' : 'flex';
    }

    const camFps = (cam.fps !== undefined ? cam.fps : (s.camera_fps || 0)).toFixed(1);
    const procFps = (metrics.processing_fps !== undefined ? metrics.processing_fps : (s.processing_fps || 0)).toFixed(1);
    const lat = (cam.latency_ms !== undefined ? cam.latency_ms : (s.camera_latency_ms || 0)).toFixed(0);

    if (DOM.overviewFpsValue) DOM.overviewFpsValue.textContent = `${camFps} FPS`;
    if (DOM.overviewHudFps) DOM.overviewHudFps.textContent = `${camFps} FPS`;
    if (DOM.telemetryFps) DOM.telemetryFps.textContent = `Cam: ${camFps} FPS`;
    if (DOM.telemetryProcFps) DOM.telemetryProcFps.textContent = `Proc: ${procFps} FPS`;
    if (DOM.telemetryLatency) DOM.telemetryLatency.textContent = `Ping: ${lat} ms`;
    if (DOM.liveResBadge && cam.last_working_resolution) {
      DOM.liveResBadge.textContent = cam.last_working_resolution;
    }
    if (DOM.selectResolutionVal && cam.last_working_resolution) {
      DOM.selectResolutionVal.textContent = cam.last_working_resolution;
    }

    // Phone Microphone Subsystem
    const micOk = audio.is_connected !== undefined ? !!audio.is_connected : !!audio.connected;
    if (DOM.micPill) {
      DOM.micPill.className = `soc-pill ${micOk ? 'pill-success' : 'pill-danger'}`;
    }
    if (DOM.micPillText) {
      DOM.micPillText.textContent = micOk ? 'PHONE MIC: STREAMING' : 'PHONE MIC: DISCONNECTED';
    }
    if (DOM.sidebarAudioDot) {
      DOM.sidebarAudioDot.className = `nav-dot ${micOk ? 'connected' : ''}`;
    }
    if (DOM.overviewMicBadge) {
      DOM.overviewMicBadge.className = `stat-badge ${micOk ? 'badge-success' : 'badge-danger'}`;
      DOM.overviewMicBadge.textContent = micOk ? 'STREAMING' : 'OFFLINE';
    }
    if (DOM.audioStateBadge) {
      DOM.audioStateBadge.className = `badge ${micOk ? 'badge-success' : 'badge-danger'}`;
      DOM.audioStateBadge.textContent = micOk ? 'STREAMING (Redmi 10)' : 'DISCONNECTED';
    }

    const rawRms = audio.current_rms !== undefined ? audio.current_rms : (audio.rms || 0);
    const rms = rawRms.toFixed(1);
    if (DOM.overviewMicRms) DOM.overviewMicRms.textContent = `${rms} RMS`;
    if (DOM.audioRmsText) DOM.audioRmsText.textContent = `${rms} RMS`;
    if (DOM.audioNoiseFloorText && audio.noise_floor !== undefined) {
      DOM.audioNoiseFloorText.textContent = audio.noise_floor.toFixed(1);
    }
    if (DOM.audioSnrText && audio.snr !== undefined) {
      DOM.audioSnrText.textContent = `${audio.snr.toFixed(2)}x`;
    }

    // Reactive Audio Meter Bar (0 - 5000 RMS scale)
    if (DOM.audioMeterFill && rawRms !== undefined) {
      const pct = Math.min(100, Math.max(0, (rawRms / 5000) * 100));
      DOM.audioMeterFill.style.width = `${pct}%`;
    }

    // Flashlight Automation Subsystem
    const flashActive = flash.is_on !== undefined ? !!flash.is_on : !!flash.active;
    const flashMode = flash.mode || (flash.auto_enabled ? 'auto' : (flashActive ? 'manual' : 'off'));
    const flashAuto = flashMode === 'auto';
    state.cameraSettings.torch = flashActive;

    const flashText = flashAuto
      ? (flashActive ? 'AUTO [TORCH ON]' : 'AUTO [TORCH OFF]')
      : (flashActive ? 'FORCE ON' : 'FORCE OFF');

    if (DOM.overviewFlashBadge) {
      DOM.overviewFlashBadge.className = `stat-badge ${flashActive ? 'badge-warning' : 'badge-primary'}`;
      DOM.overviewFlashBadge.textContent = flashText;
    }
    if (DOM.overviewFlashTrigger) {
      DOM.overviewFlashTrigger.textContent = flash.active_trigger || flash.trigger_source || 'CAMERA';
    }
    if (DOM.overviewTorchBtn) {
      DOM.overviewTorchBtn.textContent = `🔦 Torch: ${flashActive ? 'ON' : 'OFF'}`;
      DOM.overviewTorchBtn.classList.toggle('btn-warning', flashActive);
      DOM.overviewTorchBtn.classList.toggle('btn-outline', !flashActive);
    }
    if (DOM.hudTorchBtn) {
      DOM.hudTorchBtn.textContent = `🔦 Torch: ${flashActive ? 'ON' : 'OFF'}`;
      DOM.hudTorchBtn.classList.toggle('btn-primary', flashActive);
    }
    if (DOM.toggleTorchBtn) {
      DOM.toggleTorchBtn.textContent = `🔦 Torch: ${flashActive ? 'ON' : 'OFF'}`;
      DOM.toggleTorchBtn.classList.toggle('btn-warning', flashActive);
    }
    if (DOM.flashlightStatusPill) {
      DOM.flashlightStatusPill.className = `badge ${flashActive ? 'badge-warning' : 'badge-primary'}`;
      DOM.flashlightStatusPill.textContent = flashText;
    }
    if (DOM.flashlightLightingText && flash.lighting_condition) {
      DOM.flashlightLightingText.textContent = `Lighting: ${flash.lighting_condition}`;
    }

    // Flashlight mode buttons
    if (DOM.btnFlashlightAuto) DOM.btnFlashlightAuto.classList.toggle('active', flashAuto);
    if (DOM.btnFlashlightManual) DOM.btnFlashlightManual.classList.toggle('active', flashMode === 'manual' || (!flashAuto && flashActive));
    if (DOM.btnFlashlightOff) DOM.btnFlashlightOff.classList.toggle('active', flashMode === 'off' || (!flashAuto && !flashActive));

    if (DOM.overviewTorchAutoBtn) DOM.overviewTorchAutoBtn.classList.toggle('active', flashAuto);
    if (DOM.overviewTorchOnBtn) DOM.overviewTorchOnBtn.classList.toggle('active', flashMode === 'manual' || (!flashAuto && flashActive));
    if (DOM.overviewTorchOffBtn) DOM.overviewTorchOffBtn.classList.toggle('active', flashMode === 'off' || (!flashAuto && !flashActive));

    // 15-second Inactivity Countdown
    const countdown = flash.inactivity_countdown_sec !== undefined ? flash.inactivity_countdown_sec : (flash.inactivity_seconds_left || 0);
    const left = Math.max(0, countdown);
    if (DOM.flashlightCountdownText) DOM.flashlightCountdownText.textContent = `${left.toFixed(1)}s`;
    if (DOM.flashlightCountdownFill) {
      const pct = Math.min(100, Math.max(0, (left / 15.0) * 100));
      DOM.flashlightCountdownFill.style.width = `${pct}%`;
    }

    if (DOM.flashlightMotionText) DOM.flashlightMotionText.textContent = flash.motion_detected ? 'ACTIVE MOTION' : 'CLEAR';
    if (DOM.flashlightTriggerText) DOM.flashlightTriggerText.textContent = flash.active_trigger || flash.trigger_source || 'None';
    if (DOM.flashlightRequestedText) DOM.flashlightRequestedText.textContent = flashActive ? 'TORCH ON' : 'TORCH OFF';
    if (DOM.flashlightResultText) DOM.flashlightResultText.textContent = flash.last_command_result || flash.last_action_result || 'IDLE';

    // Flashlight Transition Log
    const logItems = flash.event_log || flash.recent_actions || [];
    if (DOM.flashlightLogTableBody && Array.isArray(logItems) && logItems.length > 0) {
      renderFlashlightLog(logItems);
    }

    // System Resources (CPU & RAM)
    const cpuPct = metrics.cpu_percent || 0;
    const ramPct = metrics.ram_percent || metrics.memory_percent || 0;
    const ramMb = metrics.ram_used_mb || metrics.memory_used_mb || 0;

    if (DOM.metricCpu) DOM.metricCpu.textContent = `${cpuPct}%`;
    if (DOM.metricCpuBar) DOM.metricCpuBar.style.width = `${cpuPct}%`;
    if (DOM.metricRam) DOM.metricRam.textContent = `${ramPct}% (${ramMb.toFixed(0)} MB)`;
    if (DOM.metricRamBar) DOM.metricRamBar.style.width = `${ramPct}%`;
    if (DOM.metricRamMb) DOM.metricRamMb.textContent = `${ramMb.toFixed(0)} MB`;
    if (DOM.throttleStatus) {
      DOM.throttleStatus.textContent = metrics.is_throttled ? 'Active (Throttled > 85%)' : 'Normal (Throttle > 85%)';
    }

    // Detection Center Telemetry
    if (night.threshold && DOM.detMotionThresh) DOM.detMotionThresh.textContent = night.threshold;
    if (night.min_area && DOM.detMinArea) DOM.detMinArea.textContent = `${night.min_area} px²`;
    if (night.active_mode && DOM.detActiveProfile) DOM.detActiveProfile.textContent = night.active_mode.toUpperCase();
    if (night.measured_brightness && DOM.detMeasuredLux) DOM.detMeasuredLux.textContent = `${night.measured_brightness.toFixed(1)} lux`;

    // Database Status
    const dbOk = s.database_healthy !== false;
    if (DOM.dbPill) DOM.dbPill.className = `soc-pill ${dbOk ? 'pill-info' : 'pill-danger'}`;
    if (DOM.dbStatusText) DOM.dbStatusText.textContent = dbOk ? 'DB: HEALTHY' : 'DB: ERROR';
  }

  function renderFlashlightLog(actions) {
    if (!actions || actions.length === 0) return;
    DOM.flashlightLogTableBody.innerHTML = actions.slice(-15).reverse().map(act => `
      <tr>
        <td style="font-family: monospace;">${act.timestamp ? act.timestamp.split('T')[1]?.split('.')[0] || act.timestamp : '--'}</td>
        <td><strong>${act.action || act.event || 'Transition'}</strong></td>
        <td>${act.details || act.reason || '--'}</td>
        <td><span class="badge ${act.result === 'success' || act.result === 'OK' || act.result === 'ok' ? 'badge-success' : 'badge-primary'}">${act.result || 'OK'}</span></td>
      </tr>
    `).join('');
  }

  // =========================================================================
  // Incident History & Gallery
  // =========================================================================
  async function fetchEvents() {
    try {
      const url = state.selectedCategory && state.selectedCategory !== 'all'
        ? `/api/events?category=${encodeURIComponent(state.selectedCategory)}&limit=100`
        : `/api/events?limit=100`;
      const res = await apiFetch(url);
      if (!res.ok) return;
      const data = await res.json();
      state.events = Array.isArray(data) ? data : (data.events || []);

      updateEventCounts();
      renderEventsList();
      updateLatestOverviewIncident();
    } catch (err) {
      console.warn('Failed to fetch events:', err);
    }
  }

  function updateEventCounts() {
    if (DOM.sidebarIncidentCount) {
      DOM.sidebarIncidentCount.textContent = state.events.length;
    }
    if (DOM.todayEventsCount) {
      DOM.todayEventsCount.textContent = state.events.length;
    }
    if (DOM.todayIncidentsBadge) {
      DOM.todayIncidentsBadge.textContent = `${state.events.length} Recorded`;
    }

    let counts = { all: state.events.length, Person: 0, Bird: 0, Animal: 0, Monkey: 0, Motion: 0 };
    state.events.forEach(ev => {
      const cat = ev.category || 'Motion';
      if (counts[cat] !== undefined) counts[cat]++;
    });

    if (DOM.countAll) DOM.countAll.textContent = counts.all;
    if (DOM.countPerson) DOM.countPerson.textContent = counts.Person;
    if (DOM.countBird) DOM.countBird.textContent = counts.Bird;
    if (DOM.countAnimal) DOM.countAnimal.textContent = counts.Animal;
    if (DOM.countMonkey) DOM.countMonkey.textContent = counts.Monkey;
    if (DOM.countMotion) DOM.countMotion.textContent = counts.Motion;
  }

  function getEventImageSrc(ev, tag = 'initial') {
    if (!ev) return '/static/favicon.svg';
    let p = '';
    if (ev.details && Array.isArray(ev.details.images) && ev.details.images.length > 0) {
      const imgs = ev.details.images;
      if (tag === 'final') {
        const finalObj = imgs.slice().reverse().find(i => i.tag === 'final') || imgs[imgs.length - 1];
        if (finalObj && finalObj.path) p = finalObj.path;
      } else {
        const initObj = imgs.find(i => i.tag === 'initial') || imgs[0];
        if (initObj && initObj.path) p = initObj.path;
      }
    }
    if (!p) {
      if (tag === 'final') {
        p = ev.final_snapshot_path || ev.snapshot_path || ev.image_path || '';
      } else {
        p = ev.initial_snapshot_path || ev.snapshot_path || ev.image_path || '';
      }
    }
    if (!p) return '/static/favicon.svg';
    if (p.startsWith('http://') || p.startsWith('https://')) return p;
    p = p.replace(/^\/+/, '');
    if (p.startsWith('storage/')) {
      return `/${p}`;
    }
    return `/storage/events/${p.replace(/^events\//, '')}`;
  }

  function renderEventsList() {
    if (!DOM.eventsList) return;
    DOM.eventsList.className = `incident-stream ${state.incidentViewMode}-layout`;

    let filtered = state.events;
    if (state.searchQuery) {
      const q = state.searchQuery.toLowerCase();
      filtered = filtered.filter(ev =>
        (ev.label && ev.label.toLowerCase().includes(q)) ||
        (ev.category && ev.category.toLowerCase().includes(q)) ||
        String(ev.id).includes(q)
      );
    }

    if (filtered.length === 0) {
      DOM.eventsList.innerHTML = `<div class="empty-state">No incidents match the active search or category filter.</div>`;
      return;
    }

    DOM.eventsList.innerHTML = filtered.map(ev => {
      const imgSrc = getEventImageSrc(ev, 'initial');
      const conf = ev.confidence ? `${(ev.confidence * 100).toFixed(0)}%` : '--%';
      const cat = ev.category || 'Motion';
      const timeStr = ev.timestamp ? new Date(ev.timestamp).toLocaleTimeString() : '--:--:--';
      const dateStr = ev.timestamp ? new Date(ev.timestamp).toLocaleDateString() : '';
      const hasMultiFrame = Boolean(
        (ev.details && Array.isArray(ev.details.images) && ev.details.images.length > 1) ||
        (ev.initial_snapshot_path && ev.final_snapshot_path && ev.initial_snapshot_path !== ev.final_snapshot_path)
      );

      return `
        <div class="incident-card" data-event-id="${ev.id}">
          <div class="incident-thumb-box" onclick="window.PySurveillance.inspectEvent(${ev.id})">
            <img src="${imgSrc}" alt="Incident ${ev.id}" loading="lazy" onerror="this.src='/static/favicon.svg'">
            ${hasMultiFrame ? '<span class="incident-tag-pill">2-FRAME COMPARE</span>' : ''}
          </div>
          <div class="incident-info-box">
            <div class="incident-title-row">
              <span class="badge ${getCategoryBadgeClass(cat)}">${cat}</span>
              <strong>${ev.label || cat}</strong>
              <span style="font-size: 0.75rem; color: #94a3b8;">${conf}</span>
            </div>
            <div class="incident-meta-row">
              <span>🕒 ${timeStr} ${dateStr}</span>
              <span>ID: #${ev.id}</span>
            </div>
          </div>
          <div class="incident-card-actions">
            <button class="btn btn-outline btn-sm" onclick="window.PySurveillance.inspectEvent(${ev.id})">🔍 Inspect</button>
            <button class="btn btn-outline btn-danger btn-sm" onclick="window.PySurveillance.deleteEvent(${ev.id})">🗑️</button>
          </div>
        </div>
      `;
    }).join('');
  }

  function getCategoryBadgeClass(cat) {
    if (cat === 'Person') return 'badge-danger';
    if (cat === 'Animal' || cat === 'Monkey') return 'badge-warning';
    if (cat === 'Bird') return 'badge-success';
    return 'badge-primary';
  }

  function updateLatestOverviewIncident() {
    if (state.events.length === 0) return;
    const latest = state.events[0];
    const imgSrc = getEventImageSrc(latest, 'initial');

    if (DOM.latestEventImg) DOM.latestEventImg.src = imgSrc;
    if (DOM.latestEventLabelText) DOM.latestEventLabelText.textContent = latest.label || latest.category || 'Motion';
    if (DOM.latestEventConfidence) DOM.latestEventConfidence.textContent = latest.confidence ? `${(latest.confidence * 100).toFixed(0)}%` : '--%';
    if (DOM.latestEventCategoryBadge) {
      DOM.latestEventCategoryBadge.className = `badge ${getCategoryBadgeClass(latest.category)}`;
      DOM.latestEventCategoryBadge.textContent = latest.category || 'Motion';
    }
    if (DOM.latestEventTimeBadge && latest.timestamp) {
      const t = new Date(latest.timestamp);
      DOM.latestEventTimeBadge.textContent = t.toLocaleTimeString();
      if (DOM.lastDetectionTimeText) DOM.lastDetectionTimeText.textContent = t.toLocaleTimeString();
    }
    if (DOM.viewLatestEventBtn) {
      DOM.viewLatestEventBtn.onclick = () => inspectEvent(latest.id);
    }
  }

  async function inspectEvent(id) {
    try {
      const res = await apiFetch(`/api/events/${id}`);
      if (!res.ok) {
        showToast('Failed to load incident details', 'danger');
        return;
      }
      const ev = await res.json();
      state.activeEventData = ev;

      if (DOM.eventDetailTitle) DOM.eventDetailTitle.textContent = `Incident #${ev.id} — ${ev.category || 'Event'}`;

      const initialSrc = getEventImageSrc(ev, 'initial');
      const finalSrc = getEventImageSrc(ev, 'final');
      const hasBoth = Boolean(initialSrc && finalSrc && initialSrc !== finalSrc);

      if (DOM.comparisonTabBar) {
        DOM.comparisonTabBar.style.display = hasBoth ? 'flex' : 'none';
      }
      if (DOM.sideBySideContainer) {
        DOM.sideBySideContainer.style.display = 'none';
      }
      if (DOM.singleImgContainer) {
        DOM.singleImgContainer.style.display = 'block';
      }

      if (DOM.eventDetailImg) DOM.eventDetailImg.src = finalSrc || initialSrc || '/static/favicon.svg';
      if (DOM.eventDetailInitialImg) DOM.eventDetailInitialImg.src = initialSrc;
      if (DOM.eventDetailFinalImg) DOM.eventDetailFinalImg.src = finalSrc;

      if (DOM.eventDetailCategory) {
        DOM.eventDetailCategory.className = `badge ${getCategoryBadgeClass(ev.category)}`;
        DOM.eventDetailCategory.textContent = ev.category || 'Motion';
      }
      if (DOM.eventDetailTimestamp) DOM.eventDetailTimestamp.textContent = ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '--';
      if (DOM.eventDetailConfidence) DOM.eventDetailConfidence.textContent = ev.confidence ? `${(ev.confidence * 100).toFixed(1)}%` : '--%';
      if (DOM.eventDetailLabel) DOM.eventDetailLabel.textContent = ev.label || '--';
      if (DOM.eventDetailJson) DOM.eventDetailJson.textContent = JSON.stringify(ev, null, 2);

      if (DOM.downloadEventImgBtn) {
        DOM.downloadEventImgBtn.href = finalSrc || initialSrc;
        DOM.downloadEventImgBtn.download = `incident_${ev.id}.jpg`;
      }
      if (DOM.deleteEventBtn) {
        DOM.deleteEventBtn.onclick = () => deleteEvent(ev.id);
      }

      openModal(DOM.eventDetailModal);
    } catch (err) {
      showToast('Error opening incident modal', 'danger');
    }
  }

  function initComparisonModalTabs() {
    if (DOM.btnCompInitial) {
      DOM.btnCompInitial.addEventListener('click', () => {
        if (!state.activeEventData) return;
        DOM.btnCompInitial.classList.add('active');
        DOM.btnCompFinal.classList.remove('active');
        DOM.btnCompSideBySide.classList.remove('active');
        DOM.singleImgContainer.style.display = 'block';
        DOM.sideBySideContainer.style.display = 'none';
        DOM.eventDetailImg.src = getEventImageSrc(state.activeEventData, 'initial');
      });
    }
    if (DOM.btnCompFinal) {
      DOM.btnCompFinal.addEventListener('click', () => {
        if (!state.activeEventData) return;
        DOM.btnCompFinal.classList.add('active');
        DOM.btnCompInitial.classList.remove('active');
        DOM.btnCompSideBySide.classList.remove('active');
        DOM.singleImgContainer.style.display = 'block';
        DOM.sideBySideContainer.style.display = 'none';
        DOM.eventDetailImg.src = getEventImageSrc(state.activeEventData, 'final');
      });
    }
    if (DOM.btnCompSideBySide) {
      DOM.btnCompSideBySide.addEventListener('click', () => {
        if (!state.activeEventData) return;
        DOM.btnCompSideBySide.classList.add('active');
        DOM.btnCompInitial.classList.remove('active');
        DOM.btnCompFinal.classList.remove('active');
        DOM.singleImgContainer.style.display = 'none';
        DOM.sideBySideContainer.style.display = 'flex';
        DOM.eventDetailInitialImg.src = getEventImageSrc(state.activeEventData, 'initial');
        DOM.eventDetailFinalImg.src = getEventImageSrc(state.activeEventData, 'final');
      });
    }
  }

  async function deleteEvent(id) {
    if (!confirm(`Delete incident record #${id}?`)) return;
    try {
      const res = await apiFetch(`/api/events/${id}`, { method: 'DELETE' });
      if (res.ok) {
        showToast(`Incident #${id} removed`, 'success');
        closeModal(DOM.eventDetailModal);
        fetchEvents();
      } else if (res.status === 401) {
        openPinModal();
      } else {
        showToast('Failed to delete incident', 'danger');
      }
    } catch (err) {
      showToast('Failed to delete incident', 'danger');
    }
  }

  // =========================================================================
  // Flashlight Automation Management (Overview, Live Monitoring, Automation)
  // =========================================================================
  async function setFlashlightMode(mode) {
    try {
      const res = await apiFetch('/api/flashlight/mode', {
        method: 'POST',
        body: { mode }
      });
      if (res.ok) {
        showToast(`Flashlight mode: ${mode.toUpperCase()}`, 'info');
        pollStatus();
      } else if (res.status === 401) {
        openPinModal();
      } else {
        showToast('Failed to update flashlight mode', 'danger');
      }
    } catch (err) {
      showToast('Failed to communicate with flashlight controller', 'danger');
    }
  }

  async function toggleHardwareTorch() {
    const target = !state.cameraSettings.torch;
    const mode = target ? 'manual' : 'off';
    await setFlashlightMode(mode);
  }

  function initFlashlightControls() {
    // 1. Automation Center Buttons
    if (DOM.btnFlashlightAuto) DOM.btnFlashlightAuto.addEventListener('click', () => setFlashlightMode('auto'));
    if (DOM.btnFlashlightManual) DOM.btnFlashlightManual.addEventListener('click', () => setFlashlightMode('manual'));
    if (DOM.btnFlashlightOff) DOM.btnFlashlightOff.addEventListener('click', () => setFlashlightMode('off'));

    // 2. Overview Card Pills
    if (DOM.overviewTorchAutoBtn) DOM.overviewTorchAutoBtn.addEventListener('click', () => setFlashlightMode('auto'));
    if (DOM.overviewTorchOnBtn) DOM.overviewTorchOnBtn.addEventListener('click', () => setFlashlightMode('manual'));
    if (DOM.overviewTorchOffBtn) DOM.overviewTorchOffBtn.addEventListener('click', () => setFlashlightMode('off'));

    // 3. Overview Controls Bar Torch Button
    if (DOM.overviewTorchBtn) {
      DOM.overviewTorchBtn.addEventListener('click', () => toggleHardwareTorch());
    }

    // 4. Live Monitor Cinema HUD Torch Button
    if (DOM.hudTorchBtn) {
      DOM.hudTorchBtn.addEventListener('click', () => toggleHardwareTorch());
    }

    // 5. Camera Controls Console Toggle
    if (DOM.toggleTorchBtn) {
      DOM.toggleTorchBtn.addEventListener('click', () => toggleHardwareTorch());
    }
  }

  // =========================================================================
  // Hardware & Camera Console Handlers
  // =========================================================================
  function initHardwareConsole() {
    // Master surveillance button toggle
    const toggleSurveillance = async () => {
      const target = !state.isSurveillanceArmed;
      try {
        const res = await apiFetch('/api/surveillance/toggle', {
          method: 'POST',
          body: { enabled: target, active: target }
        });
        if (res.ok) {
          state.isSurveillanceArmed = target;
          showToast(`Surveillance pipeline ${target ? 'ARMED' : 'DISARMED'}`, target ? 'success' : 'warning');
          pollStatus();
        } else if (res.status === 401) {
          openPinModal();
        }
      } catch (err) {
        showToast('Failed to toggle surveillance pipeline', 'danger');
      }
    };

    if (DOM.masterSurveillanceBtn) DOM.masterSurveillanceBtn.addEventListener('click', toggleSurveillance);
    if (DOM.camToggleSurveillanceBtn) DOM.camToggleSurveillanceBtn.addEventListener('click', toggleSurveillance);

    // Day/Night profile segmented buttons
    const setNightMode = async (mode) => {
      try {
        const res = await apiFetch('/api/night_mode', {
          method: 'POST',
          body: { mode }
        });
        if (res.ok) {
          showToast(`Profile set to ${mode.toUpperCase()}`, 'info');
          [DOM.btnNightDay, DOM.btnNightNight, DOM.btnNightAuto].forEach(b => {
            if (b) b.classList.toggle('active', b.getAttribute('data-mode') === mode);
          });
          if (DOM.hudModeBadge) DOM.hudModeBadge.textContent = `${mode.toUpperCase()} PROFILE`;
        }
      } catch (err) {
        showToast('Failed to set night mode profile', 'danger');
      }
    };
    if (DOM.btnNightDay) DOM.btnNightDay.addEventListener('click', () => setNightMode('off'));
    if (DOM.btnNightNight) DOM.btnNightNight.addEventListener('click', () => setNightMode('on'));
    if (DOM.btnNightAuto) DOM.btnNightAuto.addEventListener('click', () => setNightMode('auto'));

    // Overview refresh button
    if (DOM.overviewRefreshBtn) {
      DOM.overviewRefreshBtn.addEventListener('click', async () => {
        showToast('Refreshing system telemetry and incident stream...', 'info', 1500);
        await Promise.all([pollStatus(), fetchEvents(), fetchStorageStats()]);
        showToast('Telemetry refreshed', 'success', 2000);
      });
    }

    // Test Audio trigger
    if (DOM.testAudioBtn) {
      DOM.testAudioBtn.addEventListener('click', async () => {
        showToast('Simulating test audio trigger from Redmi 10...', 'info');
        await apiFetch('/api/microphone/test', { method: 'POST' });
        pollStatus();
      });
    }

    // Test Alarm
    if (DOM.testAlarmBtn) {
      DOM.testAlarmBtn.addEventListener('click', async () => {
        showToast('Triggering laptop audio alarm test...', 'info');
        await apiFetch('/api/alarm/test', { method: 'POST' });
      });
    }

    // Overview start/stop pipeline buttons
    if (DOM.overviewStartBtn) {
      DOM.overviewStartBtn.addEventListener('click', async () => {
        const res = await apiFetch('/api/monitoring/start', { method: 'POST' });
        if (res.ok) {
          showToast('Surveillance pipeline started', 'success');
          pollStatus();
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }
    if (DOM.overviewStopBtn) {
      DOM.overviewStopBtn.addEventListener('click', async () => {
        const res = await apiFetch('/api/monitoring/stop', { method: 'POST' });
        if (res.ok) {
          showToast('Surveillance pipeline stopped', 'warning');
          pollStatus();
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }
    if (DOM.overviewTestPushBtn) {
      DOM.overviewTestPushBtn.addEventListener('click', async () => {
        await apiFetch('/api/push/test', { method: 'POST' });
        showToast('Push alert dispatched', 'info');
      });
    }

    // Camera sliders with debounced post
    let sliderDebounce = null;
    const postCameraControls = (overrides = {}) => {
      clearTimeout(sliderDebounce);
      sliderDebounce = setTimeout(async () => {
        const payload = {
          quality: parseInt(DOM.sliderQuality.value),
          exposure_compensation: parseInt(DOM.sliderExposure.value),
          gamma: parseFloat(DOM.sliderGamma.value),
          brightness: parseInt(DOM.sliderBrightness.value),
          contrast: parseFloat(DOM.sliderContrast.value),
          white_balance: DOM.selectWhiteBalance.value,
          auto_hdr: state.cameraSettings.auto_hdr,
          night_vision: state.cameraSettings.night_vision,
          ...overrides
        };
        try {
          const res = await apiFetch('/api/camera/controls', { method: 'POST', body: payload });
          if (!res.ok && res.status === 401) {
            openPinModal();
          }
        } catch (err) {}
      }, 300);
    };

    const wireSlider = (slider, display, suffix = '') => {
      if (!slider || !display) return;
      slider.addEventListener('input', () => {
        display.textContent = `${slider.value}${suffix}`;
        postCameraControls();
      });
    };

    wireSlider(DOM.sliderQuality, DOM.sliderQualityVal, '%');
    wireSlider(DOM.sliderExposure, DOM.sliderExposureVal, '');
    wireSlider(DOM.sliderGamma, DOM.sliderGammaVal, 'x');
    wireSlider(DOM.sliderBrightness, DOM.sliderBrightnessVal, '');
    wireSlider(DOM.sliderContrast, DOM.sliderContrastVal, 'x');
    if (DOM.selectWhiteBalance) DOM.selectWhiteBalance.addEventListener('change', () => postCameraControls());

    // Resolution selection
    if (DOM.selectResolution) {
      DOM.selectResolution.addEventListener('change', async (e) => {
        const resVal = e.target.value;
        if (DOM.selectResolutionVal) DOM.selectResolutionVal.textContent = resVal;
        showToast(`Reconfiguring camera stream to ${resVal}...`, 'info', 4000);
        try {
          const res = await apiFetch('/api/camera/controls', {
            method: 'POST',
            body: { resolution: resVal }
          });
          if (res.ok) {
            const data = await res.json();
            showToast(data.message || `Resolution set to ${resVal}`, 'success');
            setStreamMode(state.streamMode);
          } else if (res.status === 401) {
            openPinModal();
          } else {
            showToast('Resolution change failed on phone', 'danger');
          }
        } catch (err) {
          showToast('Failed to apply resolution change', 'danger');
        }
      });
    }

    // Auto-HDR toggle
    if (DOM.toggleHdrBtn) {
      DOM.toggleHdrBtn.addEventListener('click', async () => {
        state.cameraSettings.auto_hdr = !state.cameraSettings.auto_hdr;
        DOM.toggleHdrBtn.textContent = `Auto-HDR: ${state.cameraSettings.auto_hdr ? 'ON' : 'OFF'}`;
        DOM.toggleHdrBtn.classList.toggle('btn-primary', state.cameraSettings.auto_hdr);
        postCameraControls({ auto_hdr: state.cameraSettings.auto_hdr });
        showToast(`Auto-HDR ${state.cameraSettings.auto_hdr ? 'enabled' : 'disabled'}`, 'info');
      });
    }

    // Night vision toggle
    if (DOM.toggleNightBtn) {
      DOM.toggleNightBtn.addEventListener('click', async () => {
        state.cameraSettings.night_vision = !state.cameraSettings.night_vision;
        DOM.toggleNightBtn.textContent = `🌙 Night Vision: ${state.cameraSettings.night_vision ? 'ON' : 'OFF'}`;
        DOM.toggleNightBtn.classList.toggle('btn-primary', state.cameraSettings.night_vision);
        postCameraControls({ night_vision: state.cameraSettings.night_vision });
        showToast(`Camera Night Vision ${state.cameraSettings.night_vision ? 'enabled' : 'disabled'}`, 'info');
      });
    }

    if (DOM.resetControlsBtn) {
      DOM.resetControlsBtn.addEventListener('click', async () => {
        const res = await apiFetch('/api/camera/reset', { method: 'POST' });
        if (res.ok) {
          showToast('Camera optical parameters reset to defaults', 'info');
          loadCameraControls();
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }

    // Hardware toggle actions
    if (DOM.testCamBtn) {
      DOM.testCamBtn.addEventListener('click', async () => {
        showToast('Probing camera stream connection...', 'info');
        const res = await apiFetch('/api/camera/test', {
          method: 'POST',
          body: {
            phone_ip: DOM.cfgPhoneIp ? DOM.cfgPhoneIp.value : '192.168.31.211',
            phone_port: DOM.cfgPhonePort ? parseInt(DOM.cfgPhonePort.value) : 8080,
            video_endpoint: '/video',
            snapshot_endpoint: '/shot.jpg'
          }
        });
        if (res.ok) {
          const data = await res.json();
          showToast(`Camera probe: ${data.state || 'ONLINE'} (HTTP ${data.snapshot_http_status || 200})`, 'success');
        } else {
          showToast('Camera probe failed: Connection refused', 'danger');
        }
      });
    }

    if (DOM.clearEventsBtn) {
      DOM.clearEventsBtn.addEventListener('click', async () => {
        if (!confirm('Are you sure you want to purge all stored incident logs?')) return;
        const res = await apiFetch('/api/events/clear', { method: 'POST' });
        if (res.ok) {
          showToast('Incident records purged', 'warning');
          fetchEvents();
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }

    // Detection Center Sliders & Apply
    if (DOM.detThresholdSlider) {
      DOM.detThresholdSlider.addEventListener('input', (e) => {
        if (DOM.detThresholdVal) DOM.detThresholdVal.textContent = e.target.value;
      });
    }
    if (DOM.detConfidenceSlider) {
      DOM.detConfidenceSlider.addEventListener('input', (e) => {
        const pct = `${Math.round(parseFloat(e.target.value) * 100)}%`;
        if (DOM.detConfidenceVal) DOM.detConfidenceVal.textContent = pct;
        if (DOM.detConfidenceDisplay) DOM.detConfidenceDisplay.textContent = pct;
      });
    }
    if (DOM.detSaveSettingsBtn) {
      DOM.detSaveSettingsBtn.addEventListener('click', async () => {
        const thresh = parseInt(DOM.detThresholdSlider.value);
        const conf = parseFloat(DOM.detConfidenceSlider.value);
        const res = await apiFetch('/api/config', {
          method: 'POST',
          body: {
            motion_threshold: thresh,
            min_confidence: conf
          }
        });
        if (res.ok) {
          showToast('Detection thresholds updated successfully', 'success');
          pollStatus();
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }

    // Incident search filter
    if (DOM.incidentSearchInput) {
      DOM.incidentSearchInput.addEventListener('input', (e) => {
        state.searchQuery = e.target.value.trim();
        renderEventsList();
      });
    }
  }

  async function loadCameraControls() {
    try {
      const res = await apiFetch('/api/camera/controls');
      if (!res.ok) return;
      const data = await res.json();
      if (DOM.sliderQuality && data.quality !== undefined) {
        DOM.sliderQuality.value = data.quality;
        DOM.sliderQualityVal.textContent = `${data.quality}%`;
      }
      if (DOM.sliderExposure && (data.exposure_compensation !== undefined || data.exposure !== undefined)) {
        const exp = data.exposure_compensation !== undefined ? data.exposure_compensation : data.exposure;
        DOM.sliderExposure.value = exp;
        DOM.sliderExposureVal.textContent = exp;
      }
      if (DOM.sliderGamma && data.gamma !== undefined) {
        DOM.sliderGamma.value = data.gamma;
        DOM.sliderGammaVal.textContent = `${data.gamma}x`;
      }
      if (DOM.sliderBrightness && data.brightness !== undefined) {
        DOM.sliderBrightness.value = data.brightness;
        DOM.sliderBrightnessVal.textContent = data.brightness;
      }
      if (DOM.sliderContrast && data.contrast !== undefined) {
        DOM.sliderContrast.value = data.contrast;
        DOM.sliderContrastVal.textContent = `${data.contrast}x`;
      }
      if (DOM.selectWhiteBalance && data.white_balance) {
        DOM.selectWhiteBalance.value = data.white_balance;
      }
      if (data.auto_hdr !== undefined) {
        state.cameraSettings.auto_hdr = !!data.auto_hdr;
        if (DOM.toggleHdrBtn) {
          DOM.toggleHdrBtn.textContent = `Auto-HDR: ${data.auto_hdr ? 'ON' : 'OFF'}`;
          DOM.toggleHdrBtn.classList.toggle('btn-primary', !!data.auto_hdr);
        }
      }
      if (data.night_vision !== undefined) {
        state.cameraSettings.night_vision = !!data.night_vision;
        if (DOM.toggleNightBtn) {
          DOM.toggleNightBtn.textContent = `🌙 Night Vision: ${data.night_vision ? 'ON' : 'OFF'}`;
          DOM.toggleNightBtn.classList.toggle('btn-primary', !!data.night_vision);
        }
      }
      if (DOM.selectResolution && data.resolution) {
        DOM.selectResolution.value = data.resolution;
        if (DOM.selectResolutionVal) DOM.selectResolutionVal.textContent = data.resolution;
      }
    } catch (err) {}
  }

  // =========================================================================
  // Notifications Center Handlers
  // =========================================================================
  async function fetchPushStatus() {
    try {
      const res = await apiFetch('/api/push/status');
      if (!res.ok) return;
      const data = await res.json();
      if (DOM.notifPushEnabled) DOM.notifPushEnabled.checked = data.enabled !== false;
      if (DOM.sidebarPushStatusTag) {
        DOM.sidebarPushStatusTag.textContent = data.enabled ? 'ACTIVE' : 'MUTED';
        DOM.sidebarPushStatusTag.className = `nav-tag ${data.enabled ? 'tag-live' : ''}`;
      }
      if (DOM.togglePushNavBtn) {
        DOM.togglePushNavBtn.classList.toggle('active', data.enabled !== false);
      }
    } catch (err) {}
  }

  function initNotificationsHandlers() {
    // Topbar bell button toggle
    if (DOM.togglePushNavBtn) {
      DOM.togglePushNavBtn.addEventListener('click', async () => {
        const cur = DOM.togglePushNavBtn.classList.contains('active');
        const next = !cur;
        const res = await apiFetch('/api/push/toggle', {
          method: 'POST',
          body: { enabled: next }
        });
        if (res.ok) {
          DOM.togglePushNavBtn.classList.toggle('active', next);
          showToast(`Browser push alerts ${next ? 'enabled' : 'disabled'}`, 'info');
          fetchPushStatus();
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }

    if (DOM.notifPushEnabled) {
      DOM.notifPushEnabled.addEventListener('change', async (e) => {
        const next = e.target.checked;
        const res = await apiFetch('/api/push/toggle', {
          method: 'POST',
          body: { enabled: next }
        });
        if (res.ok) {
          showToast(`Push alerts ${next ? 'enabled' : 'muted'}`, 'info');
          fetchPushStatus();
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }

    if (DOM.notifSoundAlarmEnabled) {
      DOM.notifSoundAlarmEnabled.addEventListener('change', async (e) => {
        const next = e.target.checked;
        const res = await apiFetch('/api/config', {
          method: 'POST',
          body: { sound_alarm_enabled: next }
        });
        if (res.ok) {
          showToast(`Host laptop alarms ${next ? 'enabled' : 'silenced'}`, 'info');
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }

    if (DOM.notifReqPermBtn) {
      DOM.notifReqPermBtn.addEventListener('click', async () => {
        if (!('Notification' in window)) {
          showToast('This browser does not support desktop notifications', 'warning');
          return;
        }
        const perm = await Notification.requestPermission();
        if (perm === 'granted') {
          showToast('Desktop notification permission granted', 'success');
        } else {
          showToast(`Notification permission: ${perm}`, 'warning');
        }
      });
    }

    if (DOM.notifTestPushBtn) {
      DOM.notifTestPushBtn.addEventListener('click', async () => {
        const res = await apiFetch('/api/push/test', { method: 'POST' });
        if (res.ok) {
          showToast('Dispatched test alert to all connected browsers', 'info');
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }

    if (DOM.notifTestAlarmBtn) {
      DOM.notifTestAlarmBtn.addEventListener('click', async () => {
        const res = await apiFetch('/api/alarm/test', { method: 'POST' });
        if (res.ok) {
          showToast('Laptop audio alarm test triggered', 'success');
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }
  }

  // =========================================================================
  // System Analytics & Storage
  // =========================================================================
  async function fetchStorageStats() {
    try {
      const res = await apiFetch('/api/storage/stats');
      if (!res.ok) return;
      const data = await res.json();

      if (DOM.analyticsDbRows) DOM.analyticsDbRows.textContent = data.total_events || 0;
      if (DOM.storageImageCount) DOM.storageImageCount.textContent = data.snapshot_count || 0;
      if (DOM.storageUsedMbText) DOM.storageUsedMbText.textContent = `${(data.storage_used_mb || 0).toFixed(1)} MB`;
      if (DOM.storageBar) DOM.storageBar.style.width = `${Math.min(100, data.storage_percent || 0)}%`;
      if (DOM.storagePercentBadge) DOM.storagePercentBadge.textContent = `${(data.storage_percent || 0).toFixed(1)}% of ${data.storage_limit_mb || 2048} MB`;
    } catch (err) {}
  }

  function initAnalyticsHandlers() {
    if (DOM.analyticsBackupBtn) {
      DOM.analyticsBackupBtn.addEventListener('click', async () => {
        showToast('Initiating online SQLite database backup...', 'info');
        const res = await apiFetch('/api/storage/backup', { method: 'POST' });
        if (res.ok) {
          const data = await res.json();
          showToast(`Hot backup created: ${data.backup_file || 'events_backup.db'}`, 'success');
          fetchStorageStats();
        } else if (res.status === 401) {
          openPinModal();
        } else {
          showToast('Backup operation failed', 'danger');
        }
      });
    }

    if (DOM.analyticsPurgeBtn) {
      DOM.analyticsPurgeBtn.addEventListener('click', async () => {
        if (!confirm('Run automatic incident retention cleanup?')) return;
        const res = await apiFetch('/api/storage/cleanup', { method: 'POST' });
        if (res.ok) {
          showToast('Retention cleanup completed', 'success');
          fetchStorageStats();
          fetchEvents();
        } else if (res.status === 401) {
          openPinModal();
        }
      });
    }
  }

  // =========================================================================
  // Settings Configuration Form
  // =========================================================================
  async function loadConfigSettings() {
    try {
      const res = await apiFetch('/api/config');
      if (!res.ok) return;
      const cfg = await res.json();

      const cam = cfg.camera || {};
      const pipe = cfg.pipeline || {};
      const alarm = cfg.alarm || {};
      const cds = alarm.cooldowns || {};
      const flash = cfg.flashlight || {};
      const storage = cfg.storage || {};

      if (DOM.cfgPhoneIp) DOM.cfgPhoneIp.value = cam.phone_ip || cfg.phone_ip || '192.168.31.211';
      if (DOM.cfgPhonePort) DOM.cfgPhonePort.value = cam.phone_port || cfg.phone_port || 8080;
      if (DOM.cfgVideoEp) DOM.cfgVideoEp.value = cam.video_endpoint || cfg.video_endpoint || '/video';
      if (DOM.cfgSnapshotEp) DOM.cfgSnapshotEp.value = cam.snapshot_endpoint || cfg.snapshot_endpoint || '/shot.jpg';
      if (DOM.cfgAudioEp) DOM.cfgAudioEp.value = cam.audio_endpoint || cfg.audio_endpoint || '/audio.wav';

      if (DOM.cfgMotionFps) DOM.cfgMotionFps.value = pipe.motion_fps || cfg.motion_fps || 8;
      if (DOM.cfgAiFps) DOM.cfgAiFps.value = pipe.ai_fps || cfg.ai_fps || 1.5;
      if (DOM.cfgMotionThresh) DOM.cfgMotionThresh.value = pipe.motion_threshold || cfg.motion_threshold || 25;
      if (DOM.cfgConfidence) DOM.cfgConfidence.value = pipe.min_confidence || cfg.min_confidence || 0.45;
      if (DOM.cfgAutoThrottle) DOM.cfgAutoThrottle.checked = pipe.auto_throttle !== false;

      if (DOM.cfgSoundEnabled) DOM.cfgSoundEnabled.checked = alarm.sound_enabled !== false;
      if (DOM.cfgCdPerson) DOM.cfgCdPerson.value = cds.person || 15;
      if (DOM.cfgCdAnimal) DOM.cfgCdAnimal.value = cds.animal || 20;
      if (DOM.cfgCdMotion) DOM.cfgCdMotion.value = cds.motion || 30;

      if (DOM.notifCdPerson) DOM.notifCdPerson.textContent = `${cds.person || 15}s cooldown`;
      if (DOM.notifCdAnimal) DOM.notifCdAnimal.textContent = `${cds.animal || 20}s cooldown`;
      if (DOM.notifCdMotion) DOM.notifCdMotion.textContent = `${cds.motion || 30}s cooldown`;

      if (DOM.cfgFlashTimeout) DOM.cfgFlashTimeout.value = flash.inactivity_timeout_sec || 15;
      if (DOM.cfgFlashLuxCutoff) DOM.cfgFlashLuxCutoff.value = flash.lux_threshold || 45;

      if (DOM.cfgRetentionDays) DOM.cfgRetentionDays.value = storage.retention_days || 7;
      if (DOM.cfgStorageLimitMb) DOM.cfgStorageLimitMb.value = storage.max_storage_mb || 2048;

      if (DOM.detThresholdSlider) {
        DOM.detThresholdSlider.value = pipe.motion_threshold || 25;
        if (DOM.detThresholdVal) DOM.detThresholdVal.textContent = pipe.motion_threshold || 25;
      }
      if (DOM.detConfidenceSlider) {
        DOM.detConfidenceSlider.value = pipe.min_confidence || 0.45;
        const pct = `${Math.round((pipe.min_confidence || 0.45) * 100)}%`;
        if (DOM.detConfidenceVal) DOM.detConfidenceVal.textContent = pct;
        if (DOM.detConfidenceDisplay) DOM.detConfidenceDisplay.textContent = pct;
      }
    } catch (err) {
      console.warn('Failed to load settings:', err);
    }
  }

  function initSettingsHandlers() {
    if (DOM.saveGlobalSettingsBtn) {
      DOM.saveGlobalSettingsBtn.addEventListener('click', async () => {
        const payload = {
          camera: {
            phone_ip: DOM.cfgPhoneIp.value.trim(),
            phone_port: parseInt(DOM.cfgPhonePort.value),
            video_endpoint: DOM.cfgVideoEp.value.trim(),
            snapshot_endpoint: DOM.cfgSnapshotEp.value.trim(),
            audio_endpoint: DOM.cfgAudioEp.value.trim()
          },
          pipeline: {
            motion_fps: parseFloat(DOM.cfgMotionFps.value),
            ai_fps: parseFloat(DOM.cfgAiFps.value),
            motion_threshold: parseInt(DOM.cfgMotionThresh.value),
            min_confidence: parseFloat(DOM.cfgConfidence.value),
            auto_throttle: DOM.cfgAutoThrottle.checked
          },
          alarm: {
            sound_enabled: DOM.cfgSoundEnabled.checked,
            cooldowns: {
              person: parseInt(DOM.cfgCdPerson.value),
              animal: parseInt(DOM.cfgCdAnimal.value),
              motion: parseInt(DOM.cfgCdMotion.value)
            }
          },
          flashlight: {
            inactivity_timeout_sec: DOM.cfgFlashTimeout ? parseFloat(DOM.cfgFlashTimeout.value) : 15.0,
            lux_threshold: DOM.cfgFlashLuxCutoff ? parseFloat(DOM.cfgFlashLuxCutoff.value) : 45.0
          },
          storage: {
            retention_days: DOM.cfgRetentionDays ? parseInt(DOM.cfgRetentionDays.value) : 7,
            max_storage_mb: DOM.cfgStorageLimitMb ? parseInt(DOM.cfgStorageLimitMb.value) : 2048
          }
        };

        if (DOM.cfgNewPin.value.trim()) {
          payload.dashboard_pin = DOM.cfgNewPin.value.trim();
        }

        try {
          const res = await apiFetch('/api/config', {
            method: 'POST',
            body: payload
          });
          if (res.ok) {
            showToast('All settings successfully saved to disk', 'success');
            DOM.cfgNewPin.value = '';
            pollStatus();
          } else if (res.status === 401) {
            openPinModal();
          } else {
            showToast('Failed to save settings', 'danger');
          }
        } catch (err) {
          showToast('Error saving settings', 'danger');
        }
      });
    }
  }

  // =========================================================================
  // PIN Authentication & Sessions
  // =========================================================================
  function updateAuthUI() {
    if (DOM.sidebarPinBtn) {
      DOM.sidebarPinBtn.title = state.isAuthenticated
        ? 'Console Unlocked (Click to Lock)'
        : 'Console Locked (Click to Unlock)';
    }
    if (DOM.sidebarPinText) {
      DOM.sidebarPinText.textContent = state.isAuthenticated ? 'PIN: Unlocked' : 'PIN: Locked';
    }
  }

  function openPinModal() {
    if (DOM.pinError) DOM.pinError.textContent = '';
    if (DOM.pinInput) DOM.pinInput.value = '';
    openModal(DOM.pinModal);
    setTimeout(() => { if (DOM.pinInput) DOM.pinInput.focus(); }, 150);
  }

  function initAuthHandlers() {
    if (DOM.sidebarPinBtn) {
      DOM.sidebarPinBtn.addEventListener('click', () => {
        if (state.isAuthenticated) {
          logoutSession();
        } else {
          openPinModal();
        }
      });
    }

    if (DOM.securityLogoutBtn) {
      DOM.securityLogoutBtn.addEventListener('click', logoutSession);
    }

    if (DOM.pinForm) {
      DOM.pinForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const pin = DOM.pinInput.value.trim();
        if (!pin) return;

        try {
          const res = await fetch('/api/auth/verify', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin }),
            credentials: 'same-origin'
          });

          if (res.ok) {
            const data = await res.json();
            state.isAuthenticated = true;
            state.sessionToken = data.token || data.session_id || '';
            state.csrfToken = data.csrf_token || '';
            localStorage.setItem('pysurv_session_token', state.sessionToken);
            updateAuthUI();
            closeModal(DOM.pinModal);
            showToast('PIN verified. Operations unlocked.', 'success');
          } else {
            if (DOM.pinError) DOM.pinError.textContent = 'Invalid PIN code. Please try again.';
          }
        } catch (err) {
          if (DOM.pinError) DOM.pinError.textContent = 'Authentication error';
        }
      });
    }
  }

  async function logoutSession() {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' });
    } catch (err) {}
    state.isAuthenticated = false;
    state.sessionToken = '';
    state.csrfToken = '';
    localStorage.removeItem('pysurv_session_token');
    updateAuthUI();
    showToast('Session locked', 'info');
  }

  // =========================================================================
  // SSE Real-Time Event Subscriber
  // =========================================================================
  function initSSE() {
    if (state.eventSource) state.eventSource.close();
    state.eventSource = new EventSource('/api/push/stream');

    state.eventSource.onopen = () => {
      if (DOM.notifSseStatusBadge) {
        DOM.notifSseStatusBadge.textContent = 'SSE Connected';
        DOM.notifSseStatusBadge.className = 'badge badge-success';
      }
    };

    state.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'incident' || data.type === 'event' || data.event || data.category) {
          showPushBanner(data);
          fetchEvents();
        } else if (data.type === 'status' || data.type === 'telemetry') {
          renderStatus(data);
        }
      } catch (e) {}
    };

    state.eventSource.onerror = () => {
      if (DOM.notifSseStatusBadge) {
        DOM.notifSseStatusBadge.textContent = 'SSE Reconnecting...';
        DOM.notifSseStatusBadge.className = 'badge badge-warning';
      }
    };
  }

  // =========================================================================
  // QR Code Modal & Mobile
  // =========================================================================
  async function loadQrCode() {
    try {
      const res = await apiFetch('/api/qr');
      if (!res.ok) return;
      const data = await res.json();
      if (DOM.qrCodeContainer && data.svg) {
        DOM.qrCodeContainer.innerHTML = data.svg;
      }
      if (DOM.phoneUrlText && data.url) {
        DOM.phoneUrlText.textContent = data.url;
      }
      if (DOM.phoneUrlLink && data.url) {
        DOM.phoneUrlLink.href = data.url;
      }
    } catch (err) {}
  }

  function initQrHandlers() {
    if (DOM.qrBtn) {
      DOM.qrBtn.addEventListener('click', () => {
        loadQrCode();
        openModal(DOM.qrModal);
      });
    }
    if (DOM.copyUrlBtn) {
      DOM.copyUrlBtn.addEventListener('click', () => {
        if (DOM.phoneUrlText) {
          navigator.clipboard.writeText(DOM.phoneUrlText.textContent);
          showToast('LAN Dashboard URL copied to clipboard', 'success');
        }
      });
    }
  }

  // =========================================================================
  // Modal Helpers
  // =========================================================================
  function openModal(modal) {
    if (modal) modal.classList.add('open');
  }

  function closeModal(modal) {
    if (modal) modal.classList.remove('open');
  }

  function initModalDismissals() {
    document.querySelectorAll('.soc-modal').forEach(modal => {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeModal(modal);
      });
    });

    document.querySelectorAll('.modal-close-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetId = btn.getAttribute('data-close');
        if (targetId) closeModal(document.getElementById(targetId));
      });
    });
  }

  // =========================================================================
  // Responsive Navigation & Sidebar Toggles
  // =========================================================================
  function initNavigation() {
    window.addEventListener('hashchange', handleHashChange);
    window.addEventListener('popstate', handleHashChange);

    DOM.navItems.forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const targetView = item.getAttribute('data-view');
        if (targetView) {
          window.location.hash = targetView;
          navigateToView(targetView);
        }
      });
    });

    if (DOM.sidebarCollapseBtn) {
      DOM.sidebarCollapseBtn.addEventListener('click', () => {
        DOM.sidebar.classList.toggle('collapsed');
      });
    }

    if (DOM.mobileMenuBtn) {
      DOM.mobileMenuBtn.addEventListener('click', () => {
        DOM.sidebar.classList.toggle('mobile-open');
      });
    }

    // Incident view mode switches
    if (DOM.viewTabTimeline) {
      DOM.viewTabTimeline.addEventListener('click', () => {
        state.incidentViewMode = 'timeline';
        DOM.viewTabTimeline.classList.add('active');
        if (DOM.viewTabGallery) DOM.viewTabGallery.classList.remove('active');
        renderEventsList();
      });
    }

    if (DOM.viewTabGallery) {
      DOM.viewTabGallery.addEventListener('click', () => {
        state.incidentViewMode = 'gallery';
        DOM.viewTabGallery.classList.add('active');
        if (DOM.viewTabTimeline) DOM.viewTabTimeline.classList.remove('active');
        renderEventsList();
      });
    }

    // Category pills
    DOM.catPills.forEach(pill => {
      pill.addEventListener('click', () => {
        DOM.catPills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        state.selectedCategory = pill.getAttribute('data-category') || 'all';
        fetchEvents();
      });
    });
  }

  // =========================================================================
  // Bootstrap & Init
  // =========================================================================
  function init() {
    cacheDom();
    initNavigation();
    initStreamPlayers();
    initFlashlightControls();
    initHardwareConsole();
    initNotificationsHandlers();
    initAnalyticsHandlers();
    initSettingsHandlers();
    initAuthHandlers();
    initQrHandlers();
    initComparisonModalTabs();
    initModalDismissals();
    initSSE();

    // Export inspect & delete functions for inline onclick handlers
    window.PySurveillance = {
      inspectEvent,
      deleteEvent
    };

    // Initial Hash View
    handleHashChange();

    // Initial Data Fetches
    pollStatus();
    fetchEvents();
    loadCameraControls();
    fetchPushStatus();

    // Timers
    state.statusPollTimer = setInterval(pollStatus, 1000);
    state.eventsPollTimer = setInterval(fetchEvents, 3000);
    state.storagePollTimer = setInterval(fetchStorageStats, 10000);

    // Initial check of authentication state
    if (state.sessionToken) {
      state.isAuthenticated = true;
    }
    updateAuthUI();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
