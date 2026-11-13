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
    pendingAction: null,
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
    activeEventData: null,
    audioCtx: null,
    browserAudioEnabled: true
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
    DOM.topbarRecBadge = document.getElementById('topbarRecBadge');
    DOM.recStateLabel = document.getElementById('recStateLabel');
    DOM.recDurationText = document.getElementById('recDurationText');
    DOM.detectionPill = document.getElementById('detectionPill');
    DOM.detectionPillText = document.getElementById('detectionPillText');
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
    DOM.overviewDetectionCard = document.getElementById('overviewDetectionCard');
    DOM.overviewDetectBadge = document.getElementById('overviewDetectBadge');
    DOM.overviewDetectVal = document.getElementById('overviewDetectVal');
    DOM.overviewDetectMeta = document.getElementById('overviewDetectMeta');
    DOM.detCatMotion = document.getElementById('detCatMotion');
    DOM.detCatPerson = document.getElementById('detCatPerson');
    DOM.detCatAnimal = document.getElementById('detCatAnimal');
    DOM.detCatBird = document.getElementById('detCatBird');
    DOM.detCatMonkey = document.getElementById('detCatMonkey');
    DOM.overviewVideoBadge = document.getElementById('overviewVideoBadge');
    DOM.overviewVideoVal = document.getElementById('overviewVideoVal');
    DOM.overviewVideoMeta = document.getElementById('overviewVideoMeta');
    DOM.videoQueueCount = document.getElementById('videoQueueCount');
    DOM.videoProcCount = document.getElementById('videoProcCount');
    DOM.videoDoneCount = document.getElementById('videoDoneCount');
    DOM.videoFailCount = document.getElementById('videoFailCount');
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
    DOM.cinemaDetectionHud = document.getElementById('cinemaDetectionHud');
    DOM.cinemaDetectBadge = document.getElementById('cinemaDetectBadge');
    DOM.cinemaDetectText = document.getElementById('cinemaDetectText');
    DOM.cinemaRecBadge = document.getElementById('cinemaRecBadge');
    DOM.cinemaRecText = document.getElementById('cinemaRecText');
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
    DOM.detectionLiveMonitorPanel = document.getElementById('detectionLiveMonitorPanel');
    DOM.detCenterStatusBadge = document.getElementById('detCenterStatusBadge');
    DOM.detCenterMotionState = document.getElementById('detCenterMotionState');
    DOM.detCenterPrimaryTarget = document.getElementById('detCenterPrimaryTarget');
    DOM.detCenterConfidence = document.getElementById('detCenterConfidence');
    DOM.detCenterLastTime = document.getElementById('detCenterLastTime');
    DOM.detCenterPillMotion = document.getElementById('detCenterPillMotion');
    DOM.detCenterPillPerson = document.getElementById('detCenterPillPerson');
    DOM.detCenterPillAnimal = document.getElementById('detCenterPillAnimal');
    DOM.detCenterPillBird = document.getElementById('detCenterPillBird');
    DOM.detCenterPillMonkey = document.getElementById('detCenterPillMonkey');
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
    DOM.notifBrowserAudioEnabled = document.getElementById('notifBrowserAudioEnabled');
    DOM.notifReqPermBtn = document.getElementById('notifReqPermBtn');
    DOM.notifPermissionStatusBadge = document.getElementById('notifPermissionStatusBadge');
    DOM.notifCdPerson = document.getElementById('notifCdPerson');
    DOM.notifCdAnimal = document.getElementById('notifCdAnimal');
    DOM.notifCdMotion = document.getElementById('notifCdMotion');
    DOM.notifEventTableBody = document.getElementById('notifEventTableBody');

    // Phone Device Telemetry & Battery
    DOM.topbarPhonePill = document.getElementById('topbarPhonePill');
    DOM.topbarPhoneBatteryIcon = document.getElementById('topbarPhoneBatteryIcon');
    DOM.topbarPhoneBatteryText = document.getElementById('topbarPhoneBatteryText');
    DOM.topbarPhoneTempText = document.getElementById('topbarPhoneTempText');
    DOM.overviewPhoneBadge = document.getElementById('overviewPhoneBadge');
    DOM.overviewPhoneBatteryVal = document.getElementById('overviewPhoneBatteryVal');
    DOM.overviewPhoneTempMeta = document.getElementById('overviewPhoneTempMeta');
    DOM.overviewPhoneSensorsStatus = document.getElementById('overviewPhoneSensorsStatus');
    DOM.livePhoneModel = document.getElementById('livePhoneModel');
    DOM.livePhoneBattery = document.getElementById('livePhoneBattery');
    DOM.livePhoneTemp = document.getElementById('livePhoneTemp');
    DOM.livePhoneVolt = document.getElementById('livePhoneVolt');
    DOM.livePhoneOptics = document.getElementById('livePhoneOptics');
    DOM.livePhoneSensorHint = document.getElementById('livePhoneSensorHint');

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
    DOM.cfgDeviceProfile = document.getElementById('cfgDeviceProfile');
    DOM.cfgPhoneIp = document.getElementById('cfgPhoneIp');
    DOM.cfgPhonePort = document.getElementById('cfgPhonePort');
    DOM.cfgVideoEp = document.getElementById('cfgVideoEp');
    DOM.cfgSnapshotEp = document.getElementById('cfgSnapshotEp');
    DOM.cfgAudioEp = document.getElementById('cfgAudioEp');
    DOM.cfgVideoUrl = document.getElementById('cfgVideoUrl');
    DOM.cfgSnapshotUrl = document.getElementById('cfgSnapshotUrl');
    DOM.cfgAudioUrl = document.getElementById('cfgAudioUrl');
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
    DOM.cfgVideoEnabled = document.getElementById('cfgVideoEnabled');
    DOM.cfgVideoInactivityTimeout = document.getElementById('cfgVideoInactivityTimeout');
    DOM.cfgVideoMaxDuration = document.getElementById('cfgVideoMaxDuration');
    DOM.cfgVideoFps = document.getElementById('cfgVideoFps');
    DOM.cfgVideoMaxExtracts = document.getElementById('cfgVideoMaxExtracts');
    DOM.cfgVideoMinSharpness = document.getElementById('cfgVideoMinSharpness');
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

    DOM.firstRunPinModal = document.getElementById('firstRunPinModal');
    DOM.firstRunPinForm = document.getElementById('firstRunPinForm');
    DOM.setupPinInput = document.getElementById('setupPinInput');
    DOM.setupPinConfirmInput = document.getElementById('setupPinConfirmInput');
    DOM.firstRunPinError = document.getElementById('firstRunPinError');
    DOM.btnSaveInitialPin = document.getElementById('btnSaveInitialPin');

    DOM.overviewAudioMeta = document.getElementById('overviewAudioMeta');
    DOM.camHostDisplay = document.getElementById('camHostDisplay');
    DOM.sidebarHostName = document.getElementById('sidebarHostName');

    DOM.eventDetailModal = document.getElementById('eventDetailModal');
    DOM.eventDetailTitle = document.getElementById('eventDetailTitle');
    DOM.comparisonTabBar = document.getElementById('comparisonTabBar');
    DOM.btnCompInitial = document.getElementById('btnCompInitial');
    DOM.btnCompFinal = document.getElementById('btnCompFinal');
    DOM.btnCompSideBySide = document.getElementById('btnCompSideBySide');
    DOM.btnCompExtracts = document.getElementById('btnCompExtracts');
    DOM.extractsCountBadge = document.getElementById('extractsCountBadge');
    DOM.singleImgContainer = document.getElementById('singleImgContainer');
    DOM.eventDetailImg = document.getElementById('eventDetailImg');
    DOM.sideBySideContainer = document.getElementById('sideBySideContainer');
    DOM.videoExtractsContainer = document.getElementById('videoExtractsContainer');
    DOM.videoExtractsGrid = document.getElementById('videoExtractsGrid');
    DOM.eventDetailInitialImg = document.getElementById('eventDetailInitialImg');
    DOM.eventDetailFinalImg = document.getElementById('eventDetailFinalImg');
    DOM.eventDetailCategory = document.getElementById('eventDetailCategory');
    DOM.eventDetailTimestamp = document.getElementById('eventDetailTimestamp');
    DOM.eventDetailConfidence = document.getElementById('eventDetailConfidence');
    DOM.eventDetailLabel = document.getElementById('eventDetailLabel');
    DOM.eventDetailMotionRatio = document.getElementById('eventDetailMotionRatio');
    DOM.eventDetailBbox = document.getElementById('eventDetailBbox');
    DOM.sideInitialTime = document.getElementById('sideInitialTime');
    DOM.sideFinalTime = document.getElementById('sideFinalTime');
    DOM.stageFrameIndicator = document.getElementById('stageFrameIndicator');
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

  function playBrowserAlertChime(category) {
    if (!state.browserAudioEnabled) return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      if (!state.audioCtx) {
        state.audioCtx = new AudioCtx();
      }
      if (state.audioCtx.state === 'suspended') {
        state.audioCtx.resume();
      }

      const now = state.audioCtx.currentTime;
      const osc = state.audioCtx.createOscillator();
      const gain = state.audioCtx.createGain();

      const isHighPriority = (category === 'Person' || category === 'Monkey' || category === 'Animal');
      osc.type = isHighPriority ? 'sawtooth' : 'sine';
      osc.frequency.setValueAtTime(isHighPriority ? 920 : 660, now);
      osc.frequency.exponentialRampToValueAtTime(isHighPriority ? 440 : 330, now + 0.3);

      gain.gain.setValueAtTime(0.25, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.35);

      osc.connect(gain);
      gain.connect(state.audioCtx.destination);

      osc.start(now);
      osc.stop(now + 0.35);
    } catch (e) {
      console.debug('Browser audio synth chime error:', e);
    }
  }

  // Register Service Worker for Native OS / Android Notification Center
  let swRegistration = null;
  async function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return null;
    try {
      swRegistration = await navigator.serviceWorker.register('/sw.js', { scope: '/' });
      console.info('PySURVEILLANCE ServiceWorker registered:', swRegistration.scope);
      return swRegistration;
    } catch (err) {
      console.warn('ServiceWorker registration error:', err);
      return null;
    }
  }

  // Handle messages posted from Service Worker notification click events
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data?.type === 'NOTIFICATION_NAVIGATE') {
        if (event.data.view) navigateToView(event.data.view);
        if (event.data.eventId && typeof window.PySurveillance?.inspectEvent === 'function') {
          window.PySurveillance.inspectEvent(event.data.eventId);
        }
      }
    });
  }

  async function dispatchBrowserNotification(type, data) {
    if (!data) return;
    const cat = data.category || (type === 'alarm' ? 'Host Alarm' : 'Motion');
    const label = data.label || cat;
    const confStr = data.confidence ? ` (${(data.confidence * 100).toFixed(0)}%)` : '';
    const title = `🚨 PySURVEILLANCE: ${cat} Detected`;
    const body = `${label}${confStr} — ${new Date().toLocaleTimeString()}`;

    // 1. Play audible Web Audio chime in browser
    playBrowserAlertChime(cat);

    // 2. Trigger native OS / Device System Notification Center
    if ('Notification' in window && Notification.permission === 'granted') {
      const notifOptions = {
        body: body,
        icon: '/static/favicon.svg',
        badge: '/static/favicon.svg',
        tag: `pysurv-${data.id || Date.now()}`,
        renotify: true,
        vibrate: [200, 100, 200, 100, 200],
        data: {
          url: '/#incidents',
          id: data.id || null
        }
      };

      let showedViaSW = false;
      if ('serviceWorker' in navigator) {
        try {
          const reg = swRegistration || (await Promise.race([
            navigator.serviceWorker.ready,
            new Promise((_, reject) => setTimeout(() => reject(new Error('SW ready timeout')), 1000))
          ]));
          if (reg && typeof reg.showNotification === 'function') {
            await reg.showNotification(title, notifOptions);
            showedViaSW = true;
          }
        } catch (swErr) {
          console.warn('ServiceWorker showNotification error/timeout, falling back to desktop Notification API:', swErr);
        }
      }

      if (!showedViaSW) {
        try {
          const n = new Notification(title, notifOptions);
          n.onclick = () => {
            window.focus();
            navigateToView('incidents');
            if (data.id && typeof window.PySurveillance?.inspectEvent === 'function') {
              window.PySurveillance.inspectEvent(data.id);
            }
            n.close();
          };
        } catch (err) {
          console.warn('Native notification fallback error:', err);
        }
      }
    }

    // 3. Show In-App Push Banner
    showPushBanner({
      id: data.id,
      title: title,
      body: body,
      category: cat
    });
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
      if (eventData.id && typeof window.PySurveillance?.inspectEvent === 'function') {
        window.PySurveillance.inspectEvent(eventData.id);
      }
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

    // Host System Telemetry
    if (s.host_system) {
      if (DOM.sidebarHostName) {
        DOM.sidebarHostName.textContent = s.host_system.hostname || 'Linux Host';
      }
      if (DOM.sidebarHostStatus) {
        DOM.sidebarHostStatus.textContent = `${s.host_system.system || 'Linux'} • Operational`;
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
    if (DOM.overviewCamMeta) {
      DOM.overviewCamMeta.textContent = `Target: ${cam.stream_url || cam.phone_ip || 'Connected'}`;
    }
    if (DOM.camHostDisplay) {
      DOM.camHostDisplay.innerHTML = `Camera: <code>${cam.stream_url || (cam.phone_ip ? cam.phone_ip + ':' + (cam.phone_port || 8080) : 'Connected')}</code>`;
    }
    if (DOM.modeDirectPhoneLink && cam.stream_url) {
      DOM.modeDirectPhoneLink.href = cam.stream_url;
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

    // Audio Subsystem
    const micOk = audio.is_connected !== undefined ? !!audio.is_connected : !!audio.connected;
    if (DOM.micPill) {
      DOM.micPill.className = `soc-pill ${micOk ? 'pill-success' : 'pill-danger'}`;
    }
    if (DOM.micPillText) {
      DOM.micPillText.textContent = micOk ? 'MIC: STREAMING' : 'MIC: DISCONNECTED';
    }
    if (DOM.sidebarAudioDot) {
      DOM.sidebarAudioDot.className = `nav-dot ${micOk ? 'connected' : ''}`;
    }
    if (DOM.overviewMicBadge) {
      DOM.overviewMicBadge.className = `stat-badge ${micOk ? 'badge-success' : 'badge-danger'}`;
      DOM.overviewMicBadge.textContent = micOk ? 'STREAMING' : 'OFFLINE';
    }
    if (DOM.overviewAudioMeta) {
      DOM.overviewAudioMeta.textContent = `Source: ${audio.source || 'Network Audio'}`;
    }
    if (DOM.audioStateBadge) {
      DOM.audioStateBadge.className = `badge ${micOk ? 'badge-success' : 'badge-danger'}`;
      DOM.audioStateBadge.textContent = micOk ? 'STREAMING' : 'DISCONNECTED';
    }
    if (DOM.audioStreamUrlText && audio.stream_url) {
      DOM.audioStreamUrlText.textContent = audio.stream_url;
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
    if (night.confidence && DOM.detConfidenceDisplay) {
      DOM.detConfidenceDisplay.textContent = `${Math.round(night.confidence * 100)}%`;
    }
    if (night.min_area && DOM.detMinArea) DOM.detMinArea.textContent = `${night.min_area} px²`;
    if (night.active_mode && DOM.detActiveProfile) DOM.detActiveProfile.textContent = night.active_mode.toUpperCase();
    if (night.measured_brightness && DOM.detMeasuredLux) DOM.detMeasuredLux.textContent = `${night.measured_brightness.toFixed(1)} lux`;

    // Camera Device Telemetry & Battery
    const phone = s.phone_device || {};
    const phoneOk = phone.is_online !== undefined ? !!phone.is_online : camOk;
    const hasSensors = !!phone.sensors_logging_enabled;
    const battLevel = phone.battery_level;
    const battTemp = phone.battery_temp;
    const battVolt = phone.battery_voltage;
    const devModel = phone.model || 'Camera Device';

    if (DOM.topbarPhonePill) {
      if (battLevel !== null && battLevel !== undefined) {
        DOM.topbarPhoneBatteryText.textContent = `BATTERY: ${battLevel}%`;
        if (DOM.topbarPhoneBatteryIcon) {
          DOM.topbarPhoneBatteryIcon.textContent = battLevel < 20 ? '🪫' : (battLevel < 50 ? '🔋' : '⚡');
        }
      } else {
        DOM.topbarPhoneBatteryText.textContent = phoneOk ? `${devModel.toUpperCase()}: ONLINE` : `${devModel.toUpperCase()}: OFFLINE`;
      }

      if (DOM.topbarPhoneTempText) {
        if (battTemp !== null && battTemp !== undefined) {
          DOM.topbarPhoneTempText.style.display = 'inline-block';
          DOM.topbarPhoneTempText.textContent = `🌡️ ${battTemp}°C`;
        } else {
          DOM.topbarPhoneTempText.style.display = 'none';
        }
      }
    }

    if (DOM.overviewPhoneBadge) {
      DOM.overviewPhoneBadge.className = `stat-badge ${phoneOk ? 'badge-primary' : 'badge-danger'}`;
      DOM.overviewPhoneBadge.textContent = phoneOk ? (hasSensors ? 'LIVE SENSORS' : 'ONLINE') : 'OFFLINE';
    }
    if (DOM.overviewPhoneBatteryVal) {
      if (battLevel !== null && battLevel !== undefined) {
        DOM.overviewPhoneBatteryVal.textContent = `${battLevel}%`;
        DOM.overviewPhoneBatteryVal.style.color = battLevel < 20 ? '#ef4444' : (battLevel < 50 ? '#f59e0b' : '#38bdf8');
      } else {
        DOM.overviewPhoneBatteryVal.textContent = phoneOk ? (phone.battery_status || 'External Power (AC/PoE)') : 'Offline';
        DOM.overviewPhoneBatteryVal.style.color = '#38bdf8';
      }
    }
    if (DOM.overviewPhoneTempMeta) {
      if (battTemp !== null && battTemp !== undefined) {
        DOM.overviewPhoneTempMeta.textContent = `Temp: ${battTemp}°C | Voltage: ${battVolt ? battVolt + ' V' : '--'}`;
      } else {
        const hostTarget = phone.phone_ip || phone.camera_host || 'Configured Stream';
        DOM.overviewPhoneTempMeta.textContent = `Model: ${devModel} | Target: ${hostTarget}`;
      }
    }
    if (DOM.overviewPhoneSensorsStatus) {
      if (hasSensors) {
        DOM.overviewPhoneSensorsStatus.innerHTML = `<span style="color: #4ade80;">● Live sensors active</span> (${phone.video_connections || 1} video stream)`;
      } else {
        DOM.overviewPhoneSensorsStatus.innerHTML = `<span style="color: #f59e0b;">ℹ️ Sensors Logging Inactive</span> • <a href="#monitoring" style="color: #38bdf8; text-decoration: underline;">How to enable</a>`;
      }
    }

    if (DOM.livePhoneModel) DOM.livePhoneModel.textContent = phone.model || 'Network Camera';
    if (DOM.livePhoneBattery) {
      DOM.livePhoneBattery.textContent = (battLevel !== null && battLevel !== undefined) ? `${battLevel}%` : 'Logging Inactive';
      if (battLevel !== null) {
        DOM.livePhoneBattery.style.color = battLevel < 20 ? '#ef4444' : (battLevel < 50 ? '#f59e0b' : '#22c55e');
      }
    }
    if (DOM.livePhoneTemp) {
      DOM.livePhoneTemp.textContent = (battTemp !== null && battTemp !== undefined) ? `${battTemp} °C` : '-- °C';
      if (battTemp !== null) {
        DOM.livePhoneTemp.style.color = battTemp > 42 ? '#ef4444' : (battTemp > 38 ? '#f59e0b' : '#38bdf8');
      }
    }
    if (DOM.livePhoneVolt) {
      DOM.livePhoneVolt.textContent = (battVolt !== null && battVolt !== undefined) ? `${battVolt} V` : '-- V';
    }
    if (DOM.livePhoneOptics) {
      DOM.livePhoneOptics.textContent = `ISO ${phone.iso || 100} • f/${phone.aperture || '1.8'} • ${phone.video_size || '1080p'}`;
    }
    if (DOM.livePhoneSensorHint) {
      DOM.livePhoneSensorHint.textContent = phone.sensor_help_hint || (hasSensors ? 'Live sensors active.' : 'In IP Webcam: Settings ➔ Data logging ➔ Log sensors to view battery % & temp.');
      DOM.livePhoneSensorHint.style.color = hasSensors ? '#4ade80' : '#94a3b8';
    }

    // =========================================================================
    // Real-Time Live Detection & Object Classification Indicators
    // =========================================================================
    const liveDet = s.live_detection || monitoring.live_detection || {};
    const threadAlive = liveDet.thread_alive !== false && monitoring.thread_alive !== false;
    const pipeError = liveDet.pipeline_error || monitoring.pipeline_error;
    const hasMotion = !!liveDet.has_motion;
    const primCat = liveDet.primary_category;
    const primLabel = liveDet.primary_label;
    const primConf = liveDet.primary_confidence !== null && liveDet.primary_confidence !== undefined ? liveDet.primary_confidence : null;
    const catSum = liveDet.categories_summary || {};
    const lastDetTs = liveDet.last_detection_timestamp || monitoring.last_detection_timestamp;

    let detState = 'clear'; // 'clear', 'motion', 'person', 'animal', 'bird', 'monkey', 'error'
    let detPillLabel = 'DETECT: CLEAR';
    let detBadgeLabel = 'NO MOTION';
    let detValLabel = 'CLEAR';
    let detMetaLabel = 'Confidence: --';

    if (!threadAlive || pipeError) {
      detState = 'error';
      detPillLabel = pipeError ? '⚠️ DETECT: RESTARTING' : '⚠️ DETECT: OFFLINE';
      detBadgeLabel = 'PIPELINE ERROR';
      detValLabel = 'RECOVERING...';
      detMetaLabel = pipeError || 'Worker thread recovering';
    } else if (hasMotion) {
      if (primCat && primCat !== 'General motion') {
        const confPct = primConf ? `${Math.round(primConf * 100)}%` : '';
        if (primCat === 'Person') {
          detState = 'person';
          detPillLabel = `🚨 PERSON ${confPct}`.trim();
        } else if (primCat.toLowerCase().includes('monkey')) {
          detState = 'monkey';
          detPillLabel = `🐒 MONKEY ${confPct}`.trim();
        } else if (primCat === 'Bird') {
          detState = 'bird';
          detPillLabel = `🦅 BIRD ${confPct}`.trim();
        } else {
          detState = 'animal';
          detPillLabel = `🐾 ANIMAL ${confPct}`.trim();
        }
        detBadgeLabel = `${primCat.toUpperCase()} DETECTED`;
        detValLabel = primLabel || primCat;
        detMetaLabel = `Confidence: ${confPct || '--%'} | Area: ${(liveDet.motion_percent || 0).toFixed(1)}%`;
      } else {
        detState = 'motion';
        const motionPct = (liveDet.motion_percent || 0).toFixed(1);
        detPillLabel = `⚡ MOTION (${motionPct}%)`;
        detBadgeLabel = 'MOTION DETECTED';
        detValLabel = `Active Area (${motionPct}%)`;
        detMetaLabel = `Analyzing frames with YOLOv8n...`;
      }
    }

    if (lastDetTs) {
      const secAgo = Math.max(0, Math.round(Date.now() / 1000 - lastDetTs));
      const timeStr = secAgo < 60 ? `${secAgo}s ago` : `${Math.floor(secAgo / 60)}m ago`;
      detMetaLabel += ` | Last: ${timeStr}`;
    }

    // Topbar Pill
    if (DOM.detectionPill) {
      DOM.detectionPill.className = `topbar-detection-pill state-${detState}`;
    }
    if (DOM.detectionPillText) {
      DOM.detectionPillText.textContent = detPillLabel;
    }

    // Cinema Screen Overlay
    if (DOM.cinemaDetectBadge) {
      DOM.cinemaDetectBadge.className = `cinema-hud-badge state-${detState === 'clear' ? 'clear' : (detState === 'motion' ? 'motion' : 'alert')}`;
    }
    if (DOM.cinemaDetectText) {
      DOM.cinemaDetectText.textContent = detPillLabel;
    }

    // Overview Card
    if (DOM.overviewDetectBadge) {
      DOM.overviewDetectBadge.className = `stat-badge ${detState === 'clear' ? 'badge-primary' : (detState === 'motion' ? 'badge-warning' : 'badge-danger')}`;
      DOM.overviewDetectBadge.textContent = detBadgeLabel;
    }
    if (DOM.overviewDetectVal) {
      DOM.overviewDetectVal.textContent = detValLabel;
      DOM.overviewDetectVal.style.color = detState === 'clear' ? 'var(--text-primary)' : (detState === 'motion' ? '#fde047' : '#f87171');
    }
    if (DOM.overviewDetectMeta) {
      DOM.overviewDetectMeta.textContent = detMetaLabel;
    }

    // Category Tags (Overview & Detection Center)
    const isMot = catSum.motion || hasMotion;
    const isPer = catSum.person || primCat === 'Person';
    const isAnim = catSum.animal || (primCat && primCat.toLowerCase().includes('animal'));
    const isBird = catSum.bird || primCat === 'Bird';
    const isMonk = catSum.monkey || (primCat && primCat.toLowerCase().includes('monkey'));

    if (DOM.detCatMotion) DOM.detCatMotion.classList.toggle('active', isMot);
    if (DOM.detCatPerson) DOM.detCatPerson.classList.toggle('active', isPer);
    if (DOM.detCatAnimal) DOM.detCatAnimal.classList.toggle('active', isAnim);
    if (DOM.detCatBird) DOM.detCatBird.classList.toggle('active', isBird);
    if (DOM.detCatMonkey) DOM.detCatMonkey.classList.toggle('active', isMonk);

    if (DOM.detCenterPillMotion) DOM.detCenterPillMotion.classList.toggle('active', isMot);
    if (DOM.detCenterPillPerson) DOM.detCenterPillPerson.classList.toggle('active', isPer);
    if (DOM.detCenterPillAnimal) DOM.detCenterPillAnimal.classList.toggle('active', isAnim);
    if (DOM.detCenterPillBird) DOM.detCenterPillBird.classList.toggle('active', isBird);
    if (DOM.detCenterPillMonkey) DOM.detCenterPillMonkey.classList.toggle('active', isMonk);

    // Detection Center Panel
    if (DOM.detCenterMotionState) {
      DOM.detCenterMotionState.textContent = hasMotion ? `Active Motion (${(liveDet.motion_percent || 0).toFixed(1)}% area)` : 'No Motion (Standby)';
      DOM.detCenterMotionState.style.color = hasMotion ? '#fde047' : 'var(--text-primary)';
    }
    if (DOM.detCenterPrimaryTarget) {
      DOM.detCenterPrimaryTarget.textContent = primLabel || (hasMotion ? 'General Motion' : 'None (Clear)');
      DOM.detCenterPrimaryTarget.style.color = primCat && primCat !== 'General motion' ? '#f87171' : (hasMotion ? '#fde047' : 'var(--text-primary)');
    }
    if (DOM.detCenterConfidence) {
      DOM.detCenterConfidence.textContent = primConf ? `${Math.round(primConf * 100)}%` : '--%';
    }
    if (DOM.detCenterLastTime) {
      DOM.detCenterLastTime.textContent = lastDetTs ? new Date(lastDetTs * 1000).toLocaleTimeString() : 'Never';
    }
    if (DOM.detCenterStatusBadge) {
      DOM.detCenterStatusBadge.className = `badge ${threadAlive ? (hasMotion ? 'badge-danger' : 'badge-primary') : 'badge-warning'}`;
      DOM.detCenterStatusBadge.textContent = threadAlive ? (hasMotion ? 'TARGET TRACKING' : 'SURVEILLANCE ACTIVE') : 'RECOVERING';
    }

    // =========================================================================
    // Motion Video Recording Subsystem & 8-State Engine Status
    // =========================================================================
    const vid = s.video_recording || monitoring.video_recording || {};
    const overallState = vid.overall_state || (vid.is_recording ? 'RECORDING' : 'IDLE');
    const isRecording = !!vid.is_recording;
    const curRecSec = vid.recording_duration_sec || 0;
    const inactRemSec = vid.inactivity_remaining_sec || 0;
    const segIdx = vid.segment_index || 1;
    const queueStats = vid.queue || {};
    const maxDur = vid.max_segment_duration_sec || 60;

    // 8 States: IDLE, RECORDING, FINALIZING, QUEUED, PROCESSING, VERIFYING, COMPLETED, FAILED
    const stateLower = overallState.toLowerCase();

    // Topbar Pill
    if (DOM.topbarRecBadge) {
      DOM.topbarRecBadge.className = `topbar-rec-pill state-${stateLower}`;
      if (DOM.recStateLabel) {
        if (overallState === 'RECORDING') {
          DOM.recStateLabel.textContent = `REC (Seg #${segIdx})`;
        } else if (overallState === 'FINALIZING') {
          DOM.recStateLabel.textContent = 'FINALIZING...';
        } else if (overallState === 'QUEUED') {
          DOM.recStateLabel.textContent = `QUEUED (${queueStats.queued || 1})`;
        } else if (overallState === 'PROCESSING') {
          DOM.recStateLabel.textContent = 'AI EXTRACTING';
        } else if (overallState === 'VERIFYING') {
          DOM.recStateLabel.textContent = 'VERIFYING';
        } else if (overallState === 'COMPLETED') {
          DOM.recStateLabel.textContent = '✓ COMPLETED';
        } else if (overallState === 'FAILED') {
          DOM.recStateLabel.textContent = '⚠️ FAILED';
        } else {
          DOM.recStateLabel.textContent = 'REC IDLE';
        }
      }
      if (DOM.recDurationText) {
        if (overallState === 'RECORDING') {
          const rm = Math.floor(curRecSec / 60);
          const rs = Math.floor(curRecSec % 60);
          DOM.recDurationText.textContent = `${rm.toString().padStart(2, '0')}:${rs.toString().padStart(2, '0')}`;
        } else {
          DOM.recDurationText.textContent = '';
        }
      }
    }

    // Cinema Screen Recording Overlay
    if (DOM.cinemaRecBadge) {
      DOM.cinemaRecBadge.className = `cinema-hud-badge state-${stateLower === 'recording' ? 'recording' : (stateLower === 'processing' || stateLower === 'verifying' ? 'processing' : 'idle')}`;
    }
    if (DOM.cinemaRecText) {
      if (overallState === 'RECORDING') {
        DOM.cinemaRecText.textContent = `REC ${curRecSec.toFixed(0)}s (Seg #${segIdx})`;
      } else {
        DOM.cinemaRecText.textContent = `REC: ${overallState}`;
      }
    }

    // Overview Card
    if (DOM.overviewVideoBadge) {
      let badgeClass = 'badge-primary';
      if (overallState === 'RECORDING') badgeClass = 'badge-danger';
      else if (overallState === 'FINALIZING' || overallState === 'QUEUED') badgeClass = 'badge-warning';
      else if (overallState === 'PROCESSING' || overallState === 'VERIFYING') badgeClass = 'badge-info';
      else if (overallState === 'COMPLETED') badgeClass = 'badge-success';
      else if (overallState === 'FAILED') badgeClass = 'badge-danger';

      DOM.overviewVideoBadge.className = `stat-badge ${badgeClass}`;
      DOM.overviewVideoBadge.textContent = overallState;
    }
    if (DOM.overviewVideoVal) {
      if (overallState === 'RECORDING') {
        DOM.overviewVideoVal.textContent = `REC: ${curRecSec.toFixed(0)}s (Seg #${segIdx})`;
        DOM.overviewVideoVal.style.color = '#ef4444';
      } else if (overallState === 'FINALIZING') {
        DOM.overviewVideoVal.textContent = 'CLOSING SEGMENT...';
        DOM.overviewVideoVal.style.color = '#f59e0b';
      } else if (overallState === 'QUEUED') {
        DOM.overviewVideoVal.textContent = `QUEUED (${queueStats.queued || 1} pending)`;
        DOM.overviewVideoVal.style.color = '#c084fc';
      } else if (overallState === 'PROCESSING') {
        DOM.overviewVideoVal.textContent = 'EXTRACTING FRAMES';
        DOM.overviewVideoVal.style.color = '#60a5fa';
      } else if (overallState === 'VERIFYING') {
        DOM.overviewVideoVal.textContent = 'VERIFYING DISK IMAGES';
        DOM.overviewVideoVal.style.color = '#22d3ee';
      } else if (overallState === 'COMPLETED') {
        DOM.overviewVideoVal.textContent = 'INCIDENT UPDATED';
        DOM.overviewVideoVal.style.color = '#4ade80';
      } else if (overallState === 'FAILED') {
        DOM.overviewVideoVal.textContent = 'PROCESSING ERROR';
        DOM.overviewVideoVal.style.color = '#ef4444';
      } else {
        DOM.overviewVideoVal.textContent = 'STANDBY';
        DOM.overviewVideoVal.style.color = 'var(--text-primary)';
      }
    }
    if (DOM.overviewVideoMeta) {
      DOM.overviewVideoMeta.textContent = isRecording
        ? `Inactivity left: ${inactRemSec.toFixed(1)}s | Max: ${maxDur.toFixed(0)}s`
        : `Max: ${maxDur.toFixed(0)}s | Inactivity: 15s`;
    }
    if (DOM.videoQueueCount) DOM.videoQueueCount.textContent = queueStats.queued || 0;
    if (DOM.videoProcCount) DOM.videoProcCount.textContent = queueStats.processing || 0;
    if (DOM.videoDoneCount) DOM.videoDoneCount.textContent = queueStats.completed || 0;
    if (DOM.videoFailCount) DOM.videoFailCount.textContent = queueStats.failed || 0;

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

      const extractCount = (ev.details && Array.isArray(ev.details.images))
        ? ev.details.images.filter(x => x.tag === 'video_extract').length
        : 0;
      let tagBadge = '';
      if (extractCount > 0) {
        tagBadge = `<span class="incident-tag-pill" style="background: rgba(14, 165, 233, 0.85); color: #fff;">🎞️ ${extractCount} EXTRACTS</span>`;
      } else if (hasMultiFrame) {
        tagBadge = '<span class="incident-tag-pill">2-FRAME COMPARE</span>';
      }

      return `
        <div class="incident-card" data-event-id="${ev.id}" onclick="window.PySurveillance.inspectEvent(${ev.id})">
          <div class="incident-thumb-box">
            <img src="${imgSrc}" alt="Incident ${ev.id}" loading="lazy" onerror="this.src='/static/favicon.svg'">
            ${tagBadge}
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
            <button class="btn btn-outline btn-sm" onclick="event.stopPropagation(); window.PySurveillance.inspectEvent(${ev.id})">🔍 Inspect</button>
            <button class="btn btn-outline btn-danger btn-sm" onclick="event.stopPropagation(); window.PySurveillance.deleteEvent(${ev.id})">🗑️</button>
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

      const allImgs = (ev.details && Array.isArray(ev.details.images)) ? ev.details.images : [];
      const extracts = allImgs.filter(x => x.tag === 'video_extract');

      if (DOM.extractsCountBadge) {
        DOM.extractsCountBadge.textContent = extracts.length;
      }
      if (DOM.btnCompExtracts) {
        DOM.btnCompExtracts.style.display = extracts.length > 0 ? 'inline-flex' : 'none';
        DOM.btnCompExtracts.classList.remove('active');
      }

      const hasMultiTab = hasBoth || extracts.length > 0;
      if (DOM.comparisonTabBar) {
        DOM.comparisonTabBar.style.display = hasMultiTab ? 'flex' : 'none';
      }
      if (DOM.btnCompInitial) {
        DOM.btnCompInitial.classList.remove('active');
        DOM.btnCompInitial.style.display = initialSrc ? 'inline-flex' : 'none';
      }
      if (DOM.btnCompFinal) {
        DOM.btnCompFinal.classList.add('active');
        DOM.btnCompFinal.style.display = finalSrc ? 'inline-flex' : 'none';
      }
      if (DOM.btnCompSideBySide) {
        DOM.btnCompSideBySide.classList.remove('active');
        DOM.btnCompSideBySide.style.display = hasBoth ? 'inline-flex' : 'none';
      }
      if (DOM.sideBySideContainer) {
        DOM.sideBySideContainer.style.display = 'none';
      }
      if (DOM.videoExtractsContainer) {
        DOM.videoExtractsContainer.style.display = 'none';
      }
      if (DOM.singleImgContainer) {
        DOM.singleImgContainer.style.display = 'flex';
      }

      renderVideoExtracts(extracts);

      if (DOM.eventDetailImg) DOM.eventDetailImg.src = finalSrc || initialSrc || '/static/favicon.svg';
      if (DOM.eventDetailInitialImg) DOM.eventDetailInitialImg.src = initialSrc;
      if (DOM.eventDetailFinalImg) DOM.eventDetailFinalImg.src = finalSrc;

      if (DOM.eventDetailCategory) {
        DOM.eventDetailCategory.className = `badge ${getCategoryBadgeClass(ev.category)}`;
        DOM.eventDetailCategory.textContent = ev.category || 'Motion';
      }
      if (DOM.eventDetailConfidence) {
        DOM.eventDetailConfidence.textContent = ev.confidence ? `${(ev.confidence * 100).toFixed(1)}%` : '--%';
      }
      if (DOM.eventDetailTimestamp) {
        DOM.eventDetailTimestamp.textContent = ev.timestamp ? new Date(ev.timestamp).toLocaleString() : '--';
      }
      if (DOM.eventDetailLabel) {
        DOM.eventDetailLabel.textContent = ev.label || ev.category || '--';
      }

      // Detection & Motion details
      const det = (ev.details && Array.isArray(ev.details.detections) && ev.details.detections.length > 0) ? ev.details.detections[0] : null;
      if (DOM.eventDetailMotionRatio) {
        if (det && det.motion_ratio !== undefined && det.motion_ratio !== null) {
          DOM.eventDetailMotionRatio.textContent = `${(det.motion_ratio * 100).toFixed(1)}% Movement Ratio`;
        } else if (ev.details && ev.details.motion_percent !== undefined) {
          DOM.eventDetailMotionRatio.textContent = `${ev.details.motion_percent}% Frame Area`;
        } else {
          DOM.eventDetailMotionRatio.textContent = 'Mask Verified';
        }
      }

      if (DOM.eventDetailBbox) {
        if (det && Array.isArray(det.box) && det.box.length === 4) {
          const [x1, y1, x2, y2] = det.box;
          DOM.eventDetailBbox.textContent = `[X:${x1}, Y:${y1}, W:${x2 - x1}, H:${y2 - y1}]`;
        } else if (ev.details && ev.details.motion_percent) {
          DOM.eventDetailBbox.textContent = `Full Motion Cluster (${ev.details.motion_percent}%)`;
        } else {
          DOM.eventDetailBbox.textContent = 'Full Frame Area';
        }
      }

      // Timestamps for side-by-side
      let initialTimeStr = 'Trigger Start';
      let finalTimeStr = 'Motion Peak';
      if (ev.details && Array.isArray(ev.details.images)) {
        const initIm = ev.details.images.find(x => x.tag === 'initial');
        const finalIm = ev.details.images.find(x => x.tag === 'final');
        if (initIm && initIm.timestamp) {
          initialTimeStr = new Date(initIm.timestamp).toLocaleTimeString();
        }
        if (finalIm && finalIm.timestamp) {
          finalTimeStr = new Date(finalIm.timestamp).toLocaleTimeString();
          if (ev.details.session_duration_sec) {
            finalTimeStr += ` (+${ev.details.session_duration_sec.toFixed(1)}s)`;
          }
        }
      } else if (ev.timestamp) {
        initialTimeStr = new Date(ev.timestamp).toLocaleTimeString();
        finalTimeStr = ev.end_timestamp ? new Date(ev.end_timestamp).toLocaleTimeString() : initialTimeStr;
      }

      if (DOM.sideInitialTime) DOM.sideInitialTime.textContent = initialTimeStr;
      if (DOM.sideFinalTime) DOM.sideFinalTime.textContent = finalTimeStr;
      if (DOM.stageFrameIndicator) {
        DOM.stageFrameIndicator.innerHTML = `<span>Frame: <strong>Peak Concluding</strong> (${finalTimeStr})</span>`;
      }

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
        if (DOM.btnCompFinal) DOM.btnCompFinal.classList.remove('active');
        if (DOM.btnCompSideBySide) DOM.btnCompSideBySide.classList.remove('active');
        if (DOM.btnCompExtracts) DOM.btnCompExtracts.classList.remove('active');
        if (DOM.singleImgContainer) DOM.singleImgContainer.style.display = 'flex';
        if (DOM.sideBySideContainer) DOM.sideBySideContainer.style.display = 'none';
        if (DOM.videoExtractsContainer) DOM.videoExtractsContainer.style.display = 'none';
        DOM.eventDetailImg.src = getEventImageSrc(state.activeEventData, 'initial');
        if (DOM.stageFrameIndicator && DOM.sideInitialTime) {
          DOM.stageFrameIndicator.innerHTML = `<span>Frame: <strong>1️⃣ Initial Trigger</strong> (${DOM.sideInitialTime.textContent})</span>`;
        }
      });
    }
    if (DOM.btnCompFinal) {
      DOM.btnCompFinal.addEventListener('click', () => {
        if (!state.activeEventData) return;
        DOM.btnCompFinal.classList.add('active');
        if (DOM.btnCompInitial) DOM.btnCompInitial.classList.remove('active');
        if (DOM.btnCompSideBySide) DOM.btnCompSideBySide.classList.remove('active');
        if (DOM.btnCompExtracts) DOM.btnCompExtracts.classList.remove('active');
        if (DOM.singleImgContainer) DOM.singleImgContainer.style.display = 'flex';
        if (DOM.sideBySideContainer) DOM.sideBySideContainer.style.display = 'none';
        if (DOM.videoExtractsContainer) DOM.videoExtractsContainer.style.display = 'none';
        DOM.eventDetailImg.src = getEventImageSrc(state.activeEventData, 'final');
        if (DOM.stageFrameIndicator && DOM.sideFinalTime) {
          DOM.stageFrameIndicator.innerHTML = `<span>Frame: <strong>2️⃣ Peak Concluding</strong> (${DOM.sideFinalTime.textContent})</span>`;
        }
      });
    }
    if (DOM.btnCompSideBySide) {
      DOM.btnCompSideBySide.addEventListener('click', () => {
        if (!state.activeEventData) return;
        DOM.btnCompSideBySide.classList.add('active');
        if (DOM.btnCompInitial) DOM.btnCompInitial.classList.remove('active');
        if (DOM.btnCompFinal) DOM.btnCompFinal.classList.remove('active');
        if (DOM.btnCompExtracts) DOM.btnCompExtracts.classList.remove('active');
        if (DOM.singleImgContainer) DOM.singleImgContainer.style.display = 'none';
        if (DOM.sideBySideContainer) DOM.sideBySideContainer.style.display = 'flex';
        if (DOM.videoExtractsContainer) DOM.videoExtractsContainer.style.display = 'none';
        DOM.eventDetailInitialImg.src = getEventImageSrc(state.activeEventData, 'initial');
        DOM.eventDetailFinalImg.src = getEventImageSrc(state.activeEventData, 'final');
        if (DOM.stageFrameIndicator) {
          DOM.stageFrameIndicator.innerHTML = `<span>Mode: <strong>🔀 Side-by-Side Dual Comparison</strong></span>`;
        }
      });
    }
    if (DOM.btnCompExtracts) {
      DOM.btnCompExtracts.addEventListener('click', () => {
        if (!state.activeEventData) return;
        DOM.btnCompExtracts.classList.add('active');
        if (DOM.btnCompInitial) DOM.btnCompInitial.classList.remove('active');
        if (DOM.btnCompFinal) DOM.btnCompFinal.classList.remove('active');
        if (DOM.btnCompSideBySide) DOM.btnCompSideBySide.classList.remove('active');
        if (DOM.singleImgContainer) DOM.singleImgContainer.style.display = 'none';
        if (DOM.sideBySideContainer) DOM.sideBySideContainer.style.display = 'none';
        if (DOM.videoExtractsContainer) DOM.videoExtractsContainer.style.display = 'block';

        const allImgs = (state.activeEventData.details && Array.isArray(state.activeEventData.details.images)) ? state.activeEventData.details.images : [];
        const extracts = allImgs.filter(x => x.tag === 'video_extract');
        if (DOM.stageFrameIndicator) {
          DOM.stageFrameIndicator.innerHTML = `<span>Mode: <strong>🎞️ Motion Video Extracts</strong> (${extracts.length} frames evaluated)</span>`;
        }
      });
    }
  }

  function renderVideoExtracts(extracts) {
    if (!DOM.videoExtractsGrid) return;
    if (!extracts || extracts.length === 0) {
      DOM.videoExtractsGrid.innerHTML = `
        <div class="empty-state" style="grid-column: 1 / -1; padding: 30px; text-align: center; color: var(--text-muted);">
          No motion video extracts attached to this incident session.
        </div>`;
      return;
    }

    DOM.videoExtractsGrid.innerHTML = extracts.map((ext, i) => {
      let imgSrc = ext.path || '';
      if (imgSrc && !imgSrc.startsWith('http') && !imgSrc.startsWith('/')) {
        imgSrc = `/${imgSrc}`;
      }
      const offsetSec = (ext.time_offset_sec !== undefined) ? `+${ext.time_offset_sec.toFixed(1)}s` : `Frame #${ext.frame_index || i + 1}`;
      const sharp = ext.sharpness ? `Sharpness: ${ext.sharpness.toFixed(0)}` : '';
      const cat = ext.category || 'Extract';
      const label = ext.label || cat;
      const conf = ext.confidence ? `${(ext.confidence * 100).toFixed(0)}%` : '';

      return `
        <div class="video-extract-card" data-idx="${i}" onclick="window.PySurveillance.viewExtractLarge('${imgSrc}', '${label.replace(/'/g, "\\'")}', '${offsetSec}')">
          <div class="video-extract-thumb-box">
            <img src="${imgSrc}" alt="${label}" loading="lazy" onerror="this.src='/static/favicon.svg'">
            <span class="extract-offset-tag">⏱️ ${offsetSec}</span>
            ${sharp ? `<span class="extract-sharpness-tag">🔍 ${sharp}</span>` : ''}
          </div>
          <div class="video-extract-info">
            <div class="video-extract-title" title="${label}">${label}</div>
            <div class="video-extract-meta">
              <span class="badge ${getCategoryBadgeClass(cat)}">${cat}</span>
              <span>${conf}</span>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  function viewExtractLarge(src, label, offset) {
    if (DOM.singleImgContainer) DOM.singleImgContainer.style.display = 'flex';
    if (DOM.sideBySideContainer) DOM.sideBySideContainer.style.display = 'none';
    if (DOM.videoExtractsContainer) DOM.videoExtractsContainer.style.display = 'none';
    if (DOM.eventDetailImg) DOM.eventDetailImg.src = src;
    if (DOM.downloadEventImgBtn) DOM.downloadEventImgBtn.href = src;
    if (DOM.stageFrameIndicator) {
      DOM.stageFrameIndicator.innerHTML = `<span>Extract: <strong>${label}</strong> (${offset})</span>`;
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
        showToast('Simulating test audio trigger...', 'info');
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
            camera_host: DOM.cfgPhoneIp ? DOM.cfgPhoneIp.value.trim() : '',
            phone_ip: DOM.cfgPhoneIp ? DOM.cfgPhoneIp.value.trim() : '',
            camera_port: DOM.cfgPhonePort ? parseInt(DOM.cfgPhonePort.value) : 8080,
            phone_port: DOM.cfgPhonePort ? parseInt(DOM.cfgPhonePort.value) : 8080,
            video_endpoint: DOM.cfgVideoEp ? DOM.cfgVideoEp.value.trim() : '/video',
            snapshot_endpoint: DOM.cfgSnapshotEp ? DOM.cfgSnapshotEp.value.trim() : '/shot.jpg',
            video_url: DOM.cfgVideoUrl ? DOM.cfgVideoUrl.value.trim() : ''
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
        if (DOM.detMotionThresh) DOM.detMotionThresh.textContent = e.target.value;
      });
    }
    if (DOM.detConfidenceSlider) {
      DOM.detConfidenceSlider.addEventListener('input', (e) => {
        const pct = `${Math.round(parseFloat(e.target.value) * 100)}%`;
        if (DOM.detConfidenceVal) DOM.detConfidenceVal.textContent = pct;
        if (DOM.detConfidenceDisplay) DOM.detConfidenceDisplay.textContent = pct;
      });
    }

    async function applyDetectionThresholds() {
      if (!DOM.detThresholdSlider || !DOM.detConfidenceSlider) return;
      const thresh = parseInt(DOM.detThresholdSlider.value, 10);
      const conf = parseFloat(DOM.detConfidenceSlider.value);
      const confPct = `${Math.round(conf * 100)}%`;

      if (DOM.detSaveSettingsBtn) {
        DOM.detSaveSettingsBtn.disabled = true;
        DOM.detSaveSettingsBtn.textContent = '⏳ Applying...';
      }

      try {
        const res = await apiFetch('/api/detection/thresholds', {
          method: 'POST',
          body: {
            motion_threshold: thresh,
            min_confidence: conf,
            detection_confidence: conf,
          }
        });

        if (res.ok) {
          if (DOM.detMotionThresh) DOM.detMotionThresh.textContent = thresh;
          if (DOM.detConfidenceDisplay) DOM.detConfidenceDisplay.textContent = confPct;
          if (DOM.cfgMotionThresh) DOM.cfgMotionThresh.value = thresh;
          if (DOM.cfgConfidence) DOM.cfgConfidence.value = conf;
          showToast(`Applied: VarThreshold ${thresh}, AI Confidence ${confPct}`, 'success');
          pollStatus();
        } else if (res.status === 401) {
          state.pendingAction = applyDetectionThresholds;
          openPinModal();
        } else {
          showToast('Failed to apply detection thresholds', 'danger');
        }
      } catch (err) {
        showToast('Error applying detection thresholds', 'danger');
      } finally {
        if (DOM.detSaveSettingsBtn) {
          DOM.detSaveSettingsBtn.disabled = false;
          DOM.detSaveSettingsBtn.textContent = '💾 Apply Detection Thresholds';
        }
      }
    }

    if (DOM.detSaveSettingsBtn) {
      DOM.detSaveSettingsBtn.addEventListener('click', applyDetectionThresholds);
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

  function checkNotificationPermission() {
    if (!('Notification' in window)) {
      if (DOM.notifPermissionStatusBadge) {
        DOM.notifPermissionStatusBadge.textContent = 'NOT SUPPORTED';
        DOM.notifPermissionStatusBadge.className = 'badge badge-warning';
      }
      return;
    }
    const perm = Notification.permission;
    if (DOM.notifPermissionStatusBadge) {
      if (perm === 'granted') {
        DOM.notifPermissionStatusBadge.textContent = '✅ ACTIVE (DEVICE NOTIFICATIONS ENABLED)';
        DOM.notifPermissionStatusBadge.className = 'badge badge-success';
        registerServiceWorker();
      } else if (perm === 'denied') {
        DOM.notifPermissionStatusBadge.textContent = '❌ BLOCKED IN BROWSER';
        DOM.notifPermissionStatusBadge.className = 'badge badge-danger';
        DOM.notifPermissionStatusBadge.title = 'Notifications are blocked. Click the lock/site settings icon in your address bar to allow.';
      } else {
        DOM.notifPermissionStatusBadge.textContent = '⚠️ NOT YET GRANTED';
        DOM.notifPermissionStatusBadge.className = 'badge badge-warning';
      }
    }
  }

  function initNotificationsHandlers() {
    checkNotificationPermission();

    if (DOM.togglePushNavBtn) {
      DOM.togglePushNavBtn.addEventListener('click', async () => {
        const currentActive = DOM.togglePushNavBtn.classList.contains('active');
        const next = !currentActive;
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

    if (DOM.notifBrowserAudioEnabled) {
      DOM.notifBrowserAudioEnabled.addEventListener('change', (e) => {
        state.browserAudioEnabled = e.target.checked;
        showToast(`Browser sound chime ${state.browserAudioEnabled ? 'enabled' : 'muted'}`, 'info');
      });
    }

    if (DOM.notifReqPermBtn) {
      DOM.notifReqPermBtn.addEventListener('click', async () => {
        if (!('Notification' in window)) {
          showToast('This device does not support push notifications', 'warning');
          return;
        }
        try {
          const perm = await Notification.requestPermission();
          checkNotificationPermission();
          if (perm === 'granted') {
            showToast('Device notifications enabled! Registering service worker...', 'success');
            await registerServiceWorker();
            await dispatchBrowserNotification('test', {
              id: 999999,
              category: 'Person',
              label: 'Device System Notifications Enabled Successfully',
              confidence: 0.99
            });
          } else if (perm === 'denied') {
            showToast('Notifications blocked. Click the lock icon in your address bar to Allow 🔒', 'danger');
          } else {
            showToast(`Notification permission: ${perm}`, 'warning');
          }
        } catch (err) {
          showToast('Failed to request notification permission', 'danger');
        }
      });
    }

    if (DOM.notifTestPushBtn) {
      DOM.notifTestPushBtn.addEventListener('click', async () => {
        // Immediate local dispatch for instant visual, audio, and device drawer push
        await dispatchBrowserNotification('test', {
          id: `test-${Date.now()}`,
          category: 'Person',
          label: 'Test Alert: Person Detected near Monitored Perimeter',
          confidence: 0.98
        });

        // Also broadcast via backend SSE
        try {
          const res = await apiFetch('/api/push/test', { method: 'POST' });
          if (res.ok) {
            showToast('Test push notification dispatched to connected devices!', 'success');
          } else if (res.status === 401) {
            openPinModal();
          }
        } catch (err) {}
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

      if (DOM.cfgPhoneIp) DOM.cfgPhoneIp.value = cam.camera_host || cam.phone_ip || cfg.camera_host || cfg.phone_ip || '';
      if (DOM.cfgPhonePort) DOM.cfgPhonePort.value = cam.camera_port || cam.phone_port || cfg.camera_port || cfg.phone_port || 8080;
      if (DOM.cfgVideoEp) DOM.cfgVideoEp.value = cam.video_endpoint || cfg.video_endpoint || '/video';
      if (DOM.cfgSnapshotEp) DOM.cfgSnapshotEp.value = cam.snapshot_endpoint || cfg.snapshot_endpoint || '/shot.jpg';
      if (DOM.cfgAudioEp) DOM.cfgAudioEp.value = cam.audio_endpoint || cfg.audio_endpoint || '/audio.wav';
      if (DOM.cfgVideoUrl) DOM.cfgVideoUrl.value = cam.video_url || '';
      if (DOM.cfgSnapshotUrl) DOM.cfgSnapshotUrl.value = cam.snapshot_url || '';
      if (DOM.cfgAudioUrl) DOM.cfgAudioUrl.value = cam.audio_url || '';
      if (DOM.cfgDeviceProfile) DOM.cfgDeviceProfile.value = cam.device_profile || 'auto';

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

      const vid = cfg.video_recording || {};
      if (DOM.cfgVideoEnabled) DOM.cfgVideoEnabled.checked = vid.enabled !== false;
      if (DOM.cfgVideoInactivityTimeout) DOM.cfgVideoInactivityTimeout.value = vid.inactivity_timeout_sec || 15;
      if (DOM.cfgVideoMaxDuration) DOM.cfgVideoMaxDuration.value = vid.max_segment_duration_sec || 600;
      if (DOM.cfgVideoFps) DOM.cfgVideoFps.value = vid.recording_fps || 10;
      if (DOM.cfgVideoMaxExtracts) DOM.cfgVideoMaxExtracts.value = vid.max_extracted_frames || 6;
      if (DOM.cfgVideoMinSharpness) DOM.cfgVideoMinSharpness.value = vid.min_sharpness || 35;

      // Query live thresholds from detection subsystem
      try {
        const dRes = await apiFetch('/api/detection/thresholds');
        if (dRes.ok) {
          const dData = await dRes.json();
          if (dData.motion_threshold !== undefined) {
            pipe.motion_threshold = dData.motion_threshold;
          }
          if (dData.detection_confidence !== undefined) {
            pipe.detection_confidence = dData.detection_confidence;
            pipe.min_confidence = dData.detection_confidence;
          }
        }
      } catch (e) {}

      const activeThresh = pipe.motion_threshold || 25;
      const activeConf = pipe.detection_confidence || pipe.min_confidence || 0.45;
      const confPct = `${Math.round(activeConf * 100)}%`;

      if (DOM.detThresholdSlider) {
        DOM.detThresholdSlider.value = activeThresh;
        if (DOM.detThresholdVal) DOM.detThresholdVal.textContent = activeThresh;
        if (DOM.detMotionThresh) DOM.detMotionThresh.textContent = activeThresh;
      }
      if (DOM.detConfidenceSlider) {
        DOM.detConfidenceSlider.value = activeConf;
        if (DOM.detConfidenceVal) DOM.detConfidenceVal.textContent = confPct;
        if (DOM.detConfidenceDisplay) DOM.detConfidenceDisplay.textContent = confPct;
      }
      if (DOM.cfgMotionThresh) DOM.cfgMotionThresh.value = activeThresh;
      if (DOM.cfgConfidence) DOM.cfgConfidence.value = activeConf;
    } catch (err) {
      console.warn('Failed to load settings:', err);
    }
  }

  function initSettingsHandlers() {
    if (DOM.saveGlobalSettingsBtn) {
      DOM.saveGlobalSettingsBtn.addEventListener('click', async () => {
        const payload = {
          camera: {
            camera_host: DOM.cfgPhoneIp ? DOM.cfgPhoneIp.value.trim() : '',
            phone_ip: DOM.cfgPhoneIp ? DOM.cfgPhoneIp.value.trim() : '',
            camera_port: DOM.cfgPhonePort ? parseInt(DOM.cfgPhonePort.value) : 8080,
            phone_port: DOM.cfgPhonePort ? parseInt(DOM.cfgPhonePort.value) : 8080,
            video_endpoint: DOM.cfgVideoEp ? DOM.cfgVideoEp.value.trim() : '/video',
            snapshot_endpoint: DOM.cfgSnapshotEp ? DOM.cfgSnapshotEp.value.trim() : '/shot.jpg',
            audio_endpoint: DOM.cfgAudioEp ? DOM.cfgAudioEp.value.trim() : '/audio.wav',
            video_url: DOM.cfgVideoUrl ? DOM.cfgVideoUrl.value.trim() : '',
            snapshot_url: DOM.cfgSnapshotUrl ? DOM.cfgSnapshotUrl.value.trim() : '',
            audio_url: DOM.cfgAudioUrl ? DOM.cfgAudioUrl.value.trim() : '',
            device_profile: DOM.cfgDeviceProfile ? DOM.cfgDeviceProfile.value : 'auto'
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
          },
          video_recording: {
            enabled: DOM.cfgVideoEnabled ? DOM.cfgVideoEnabled.checked : true,
            inactivity_timeout_sec: DOM.cfgVideoInactivityTimeout ? parseFloat(DOM.cfgVideoInactivityTimeout.value) : 15.0,
            max_segment_duration_sec: DOM.cfgVideoMaxDuration ? parseFloat(DOM.cfgVideoMaxDuration.value) : 600.0,
            recording_fps: DOM.cfgVideoFps ? parseFloat(DOM.cfgVideoFps.value) : 10.0,
            max_extracted_frames: DOM.cfgVideoMaxExtracts ? parseInt(DOM.cfgVideoMaxExtracts.value) : 6,
            min_sharpness: DOM.cfgVideoMinSharpness ? parseFloat(DOM.cfgVideoMinSharpness.value) : 35.0
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

  function openFirstRunPinModal() {
    if (DOM.firstRunPinError) DOM.firstRunPinError.textContent = '';
    if (DOM.setupPinInput) DOM.setupPinInput.value = '';
    if (DOM.setupPinConfirmInput) DOM.setupPinConfirmInput.value = '';
    openModal(DOM.firstRunPinModal);
    setTimeout(() => { if (DOM.setupPinInput) DOM.setupPinInput.focus(); }, 150);
  }

  async function checkAuthStatus() {
    try {
      const res = await fetch('/api/auth/status', { credentials: 'same-origin' });
      if (res.ok) {
        const auth = await res.json();
        if (auth.pin_initialized === false) {
          openFirstRunPinModal();
        } else if (auth.is_authenticated) {
          state.isAuthenticated = true;
          updateAuthUI();
        }
      }
    } catch (e) {
      console.warn('Auth status check error:', e);
    }
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

    if (DOM.firstRunPinForm) {
      DOM.firstRunPinForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const pin = DOM.setupPinInput ? DOM.setupPinInput.value.trim() : '';
        const confirmPin = DOM.setupPinConfirmInput ? DOM.setupPinConfirmInput.value.trim() : '';
        if (!pin || pin.length < 4) {
          if (DOM.firstRunPinError) DOM.firstRunPinError.textContent = 'PIN must be at least 4 characters long.';
          return;
        }
        if (pin !== confirmPin) {
          if (DOM.firstRunPinError) DOM.firstRunPinError.textContent = 'PIN and Confirmation PIN do not match.';
          return;
        }

        try {
          const res = await fetch('/api/auth/setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pin: pin, confirm_pin: confirmPin }),
            credentials: 'same-origin'
          });
          const data = await res.json();
          if (res.ok && data.success) {
            state.isAuthenticated = true;
            state.sessionToken = data.token || data.session_id || '';
            state.csrfToken = data.csrf_token || '';
            localStorage.setItem('pysurv_session_token', state.sessionToken);
            updateAuthUI();
            closeModal(DOM.firstRunPinModal);
            showToast('Master PIN initialized. Console unlocked.', 'success');
          } else {
            if (DOM.firstRunPinError) DOM.firstRunPinError.textContent = data.message || 'Initialization failed.';
          }
        } catch (err) {
          if (DOM.firstRunPinError) DOM.firstRunPinError.textContent = 'Network or server error during PIN setup.';
        }
      });
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
            if (typeof state.pendingAction === 'function') {
              const pending = state.pendingAction;
              state.pendingAction = null;
              try {
                await pending();
              } catch (actErr) {
                console.warn('Failed executing pending action after PIN verify:', actErr);
              }
            }
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

    const handleIncomingMessage = (type, data) => {
      if (type === 'detection' || type === 'detection_update' || type === 'alarm' || type === 'test') {
        dispatchBrowserNotification(type, data);
        fetchEvents();
        pollStatus();
      } else if (type === 'thresholds_updated') {
        if (data.motion_threshold !== undefined) {
          if (DOM.detThresholdSlider) DOM.detThresholdSlider.value = data.motion_threshold;
          if (DOM.detThresholdVal) DOM.detThresholdVal.textContent = data.motion_threshold;
          if (DOM.detMotionThresh) DOM.detMotionThresh.textContent = data.motion_threshold;
        }
        if (data.detection_confidence !== undefined) {
          const pct = `${Math.round(data.detection_confidence * 100)}%`;
          if (DOM.detConfidenceSlider) DOM.detConfidenceSlider.value = data.detection_confidence;
          if (DOM.detConfidenceVal) DOM.detConfidenceVal.textContent = pct;
          if (DOM.detConfidenceDisplay) DOM.detConfidenceDisplay.textContent = pct;
        }
      } else if (type === 'event_completed') {
        fetchEvents();
        pollStatus();
      } else if (type === 'recording_started' || type === 'recording_stopped' || type === 'segment_rotated') {
        pollStatus();
      } else if (type === 'video_job_queued' || type === 'video_job_processing' || type === 'video_job_verifying') {
        pollStatus();
      } else if (type === 'video_job_completed') {
        pollStatus();
        fetchEvents();
        if (state.activeEventData && state.activeEventData.id === data.event_id) {
          inspectEvent(data.event_id);
        }
      } else if (type === 'video_job_failed') {
        pollStatus();
      } else if (type === 'push_config') {
        fetchPushStatus();
      } else if (type === 'status' || type === 'telemetry') {
        renderStatus(data);
      }
    };

    state.eventSource.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const type = payload.type || 'detection';
        const data = payload.data || payload;
        handleIncomingMessage(type, data);
      } catch (e) {}
    };

    // Explicit listeners for SSE named event streams
    ['detection', 'detection_update', 'event_completed', 'alarm', 'push_config', 'test', 'thresholds_updated', 'recording_started', 'recording_stopped', 'segment_rotated', 'video_job_queued', 'video_job_processing', 'video_job_verifying', 'video_job_completed', 'video_job_failed', 'video_config_updated'].forEach(evt => {
      state.eventSource.addEventListener(evt, (e) => {
        try {
          const data = JSON.parse(e.data);
          handleIncomingMessage(evt, data);
        } catch (err) {}
      });
    });

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
      deleteEvent,
      viewExtractLarge,
      navigateToView,
      dispatchBrowserNotification
    };

    // Initial Hash View
    handleHashChange();

    // Initial Data Fetches
    pollStatus();
    fetchEvents();
    loadCameraControls();
    fetchPushStatus();
    loadConfigSettings();
    registerServiceWorker();

    // Timers
    state.statusPollTimer = setInterval(pollStatus, 1000);
    state.eventsPollTimer = setInterval(fetchEvents, 3000);
    state.storagePollTimer = setInterval(fetchStorageStats, 10000);

    // Initial check of authentication state
    if (state.sessionToken) {
      state.isAuthenticated = true;
    }
    updateAuthUI();
    checkAuthStatus();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
