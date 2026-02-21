(function () {
  const initialStateNode = document.getElementById("initial-state");
  if (!initialStateNode) {
    return;
  }

  const initialState = JSON.parse(initialStateNode.textContent || "{}");
  const state = {
    tab: initialState.tab || "all",
    query: "",
    chats: initialState.chats || [],
    counts: initialState.counts || { all: 0, groups: 0, archived: 0 },
    selectedChatId: initialState.selected_chat_id || null,
    messages: initialState.messages || [],
    nextBefore: initialState.next_before || null,
    loadingOlder: false,
    loadingChats: false,
    hasMoreChats: (initialState.chats || []).length >= 100,
    chatOffset: (initialState.chats || []).length,
    chatPageSize: 200,
    infoCache: {},
    messageRequestToken: 0,
  };

  const SIDEBAR_WIDTH_KEY = "whatsapp_viewer_sidebar_width";

  const tabsContainer = document.getElementById("chat-tabs");
  const searchInput = document.getElementById("chat-search");
  const chatListNode = document.getElementById("chat-list");
  const chatTitleNode = document.getElementById("chat-title");
  const chatHeaderAvatarNode = document.getElementById("chat-header-avatar");
  const chatBackButton = document.getElementById("chat-back-button");
  const chatContactButton = document.getElementById("chat-contact-button");
  const messagesNode = document.getElementById("messages");
  const chatPanel = document.querySelector(".chat-panel");
  const sidebarResizer = document.getElementById("sidebar-resizer");

  const infoModal = document.getElementById("info-modal");
  const infoCloseButton = document.getElementById("info-close-button");
  const infoTitle = document.getElementById("info-title");
  const infoTagline = document.getElementById("info-tagline");
  const infoNumber = document.getElementById("info-number");
  const infoType = document.getElementById("info-type");
  const infoUnread = document.getElementById("info-unread");
  const infoArchived = document.getElementById("info-archived");
  const infoMuted = document.getElementById("info-muted");
  const infoAvatar = document.getElementById("info-avatar");
  const infoMain = infoModal.querySelector(".info-main");
  const groupInfoNav = document.getElementById("group-info-nav");
  const infoViewInfo = document.getElementById("info-view-info");
  const infoViewMembers = document.getElementById("info-view-members");
  const groupSection = document.getElementById("group-info-section");
  const groupCreator = document.getElementById("group-creator");
  const groupOwner = document.getElementById("group-owner");
  const groupMemberCount = document.getElementById("group-member-count");
  const groupMemberCountSummary = document.getElementById("group-member-count-summary");
  const groupMembers = document.getElementById("group-members");
  const imageViewerModal = document.getElementById("image-viewer-modal");
  const imageViewerCloseButton = document.getElementById("image-viewer-close");
  const imageViewerImage = document.getElementById("image-viewer-image");
  const imageViewerCaption = document.getElementById("image-viewer-caption");

  const escapeHtml = (value) =>
    String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  const formatMessageText = (value, mentions = []) => {
    const source = String(value || "");
    if (!source) {
      return "";
    }

    const mentionMap = new Map(
      (mentions || [])
        .map((mention) => [String(mention.token || ""), String(mention.label || "").trim()])
        .filter(([token]) => token)
    );
    const tokenPattern = /(https?:\/\/[^\s<]+|www\.[^\s<]+|@[0-9]{6,20})/gi;

    let cursor = 0;
    let output = "";
    for (const match of source.matchAll(tokenPattern)) {
      const token = match[0];
      const tokenIndex = match.index ?? 0;
      output += escapeHtml(source.slice(cursor, tokenIndex));

      if (/^@[0-9]{6,20}$/i.test(token)) {
        const displayLabel = mentionMap.get(token) || token.slice(1);
        output += `<span class="message-mention">@${escapeHtml(displayLabel)}</span>`;
      } else {
        let urlToken = token;
        let trailing = "";
        while (/[),.!?;:]$/.test(urlToken)) {
          trailing = urlToken.slice(-1) + trailing;
          urlToken = urlToken.slice(0, -1);
        }
        if (urlToken) {
          const href = urlToken.toLowerCase().startsWith("www.") ? `https://${urlToken}` : urlToken;
          output += `<a class="message-link" href="${href}" target="_blank" rel="noopener noreferrer">${escapeHtml(
            urlToken
          )}</a>${escapeHtml(trailing)}`;
        } else {
          output += escapeHtml(token);
        }
      }
      cursor = tokenIndex + token.length;
    }
    output += escapeHtml(source.slice(cursor));
    return output;
  };

  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  const openMobileChatPanel = () => {
    if (window.innerWidth <= 980 && chatPanel) {
      chatPanel.classList.add("is-open");
    }
  };

  const closeMobileChatPanel = () => {
    if (chatPanel) {
      chatPanel.classList.remove("is-open");
    }
  };

  const formatDate = (value) => {
    if (!value) {
      return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    return date.toLocaleString([], {
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  const formatShortDate = (value) => {
    if (!value) {
      return "";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    return date.toLocaleString([], {
      year: "numeric",
      month: "numeric",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  const initialsFromName = (name) => {
    const cleaned = (name || "")
      .trim()
      .replaceAll(/\s+/g, " ");
    if (!cleaned) {
      return "?";
    }
    const parts = cleaned.split(" ");
    if (parts.length === 1) {
      return parts[0].slice(0, 2).toUpperCase();
    }
    return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
  };

  const hashColor = (text) => {
    let hash = 0;
    for (let i = 0; i < text.length; i += 1) {
      hash = text.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash % 360);
    return `hsl(${hue} 55% 42%)`;
  };

  const senderColorFromKey = (key) => {
    let hash = 0;
    for (let i = 0; i < key.length; i += 1) {
      hash = key.charCodeAt(i) + ((hash << 5) - hash);
    }
    const hue = Math.abs(hash % 360);
    return `hsl(${hue} 72% 66%)`;
  };

  const avatarMarkup = (chat, sizeClass) => {
    const label = chat.chat_name || chat.contact_jid || "Unknown";
    if (chat.avatar && chat.avatar.available && chat.avatar.kind === "image") {
      return `<span class="avatar ${sizeClass}"><img src="${escapeHtml(chat.avatar.url)}" alt="${escapeHtml(label)}"></span>`;
    }
    const initials = initialsFromName(label);
    const color = hashColor(label);
    return `<span class="avatar ${sizeClass}" style="background:${escapeHtml(color)}">${escapeHtml(initials)}</span>`;
  };

  const memberAvatarMarkup = (member, sizeClass) => {
    const label = member.name || member.jid || "Unknown";
    if (member.avatar && member.avatar.available && member.avatar.kind === "image") {
      return `<span class="avatar ${sizeClass}"><img src="${escapeHtml(member.avatar.url)}" alt="${escapeHtml(label)}"></span>`;
    }
    const initials = initialsFromName(label);
    const color = hashColor(label);
    return `<span class="avatar ${sizeClass}" style="background:${escapeHtml(color)}">${escapeHtml(initials)}</span>`;
  };

  const memberPhoneLabel = (member) => {
    const explicitPhone = String(member.phone || "").trim();
    if (explicitPhone) {
      return explicitPhone;
    }
    const jid = String(member.jid || "").trim();
    if (!jid) {
      return "";
    }
    const normalizedJid = jid.toLowerCase();
    if (normalizedJid.endsWith("@lid")) {
      return "";
    }
    if (
      normalizedJid.includes("@") &&
      !(
        normalizedJid.endsWith("@s.whatsapp.net") ||
        normalizedJid.endsWith("@c.us")
      )
    ) {
      return "";
    }
    if (!normalizedJid.includes("@")) {
      return "";
    }
    const localPart = jid.includes("@") ? jid.split("@", 1)[0] : jid;
    const digits = localPart.replace(/\D/g, "");
    if (digits.length < 8) {
      return "";
    }
    return `+${digits}`;
  };

  const renderAvatarNode = (targetNode, chat, fallbackLabel) => {
    const label = fallbackLabel || chat.chat_name || chat.contact_jid || "Unknown";
    if (chat.avatar && chat.avatar.available && chat.avatar.kind === "image") {
      targetNode.innerHTML = `<img src="${escapeHtml(chat.avatar.url)}" alt="${escapeHtml(label)}">`;
      targetNode.style.background = "transparent";
      return;
    }
    targetNode.innerHTML = escapeHtml(initialsFromName(label));
    targetNode.style.background = hashColor(label);
  };

  const applySystemTheme = () => {
    const prefersLight = window.matchMedia("(prefers-color-scheme: light)").matches;
    document.documentElement.dataset.theme = prefersLight ? "light" : "dark";
  };

  const syncThemeListener = () => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: light)");
    applySystemTheme();
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", applySystemTheme);
      return;
    }
    mediaQuery.addListener(applySystemTheme);
  };

  const setTabCounts = () => {
    document.getElementById("count-all").textContent = String(state.counts.all || 0);
    document.getElementById("count-groups").textContent = String(state.counts.groups || 0);
    document.getElementById("count-archived").textContent = String(state.counts.archived || 0);
  };

  const syncTabUI = () => {
    tabsContainer.querySelectorAll(".tab").forEach((tabButton) => {
      tabButton.classList.toggle("is-active", tabButton.dataset.tab === state.tab);
    });
  };

  const updateUrl = () => {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", state.tab);
    if (state.selectedChatId) {
      url.searchParams.set("chat", String(state.selectedChatId));
    } else {
      url.searchParams.delete("chat");
    }
    window.history.replaceState({}, "", `${url.pathname}?${url.searchParams.toString()}`);
  };

  const selectedChat = () => state.chats.find((chat) => chat.chat_id === state.selectedChatId);

  const renderChats = () => {
    if (!state.chats.length) {
      chatListNode.innerHTML = '<li class="empty-state">No chats found.</li>';
      return;
    }

    const chatRows = state.chats
      .map((chat) => {
        const isSelected = chat.chat_id === state.selectedChatId;
        const badge = chat.unread_count > 0 ? `<span class="unread-badge">${chat.unread_count}</span>` : "";
        return `
          <li class="chat-row ${isSelected ? "is-selected" : ""}" data-chat-id="${chat.chat_id}">
            <div class="chat-row-main">
              ${avatarMarkup(chat, "avatar-sm")}
              <div class="chat-row-content">
                <div class="chat-topline">
                  <span class="chat-name">${escapeHtml(chat.chat_name)}</span>
                  <span class="chat-time">${escapeHtml(formatShortDate(chat.last_message_date))}</span>
                </div>
                <div class="chat-bottomline">
                  <span class="chat-preview">${escapeHtml(chat.last_message_text || "")}</span>
                  ${badge}
                </div>
              </div>
            </div>
          </li>
        `;
      })
      .join("");

    const loadingRow = state.loadingChats
      ? '<li class="empty-state">Loading more chats...</li>'
      : state.hasMoreChats
        ? '<li class="empty-state">Scroll to load more</li>'
        : "";
    chatListNode.innerHTML = `${chatRows}${loadingRow}`;
  };

  const renderMedia = (media) => {
    if (!media) {
      return "";
    }
    if (!media.available) {
      return `<div class="media"><a href="${escapeHtml(media.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(
        media.file_name
      )} (missing)</a></div>`;
    }
    if (media.kind === "image") {
      return `
        <div class="media">
          <button type="button" class="media-image-trigger" data-image-url="${escapeHtml(media.url)}" data-image-name="${escapeHtml(
            media.file_name
          )}">
            <img class="message-image-thumb" src="${escapeHtml(media.url)}" alt="${escapeHtml(media.file_name)}">
          </button>
        </div>
      `;
    }
    if (media.kind === "video") {
      return `<div class="media"><video controls src="${escapeHtml(media.url)}"></video></div>`;
    }
    if (media.kind === "audio") {
      return `<div class="media"><audio controls src="${escapeHtml(media.url)}"></audio></div>`;
    }
    return `<div class="media"><a href="${escapeHtml(media.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(
      media.file_name
    )}</a></div>`;
  };

  const renderVCard = (vcard) => {
    if (!vcard) {
      return "";
    }
    const name = escapeHtml(vcard.name || "Contact");
    const title = vcard.title ? `<div class="vcard-subtitle">${escapeHtml(vcard.title)}</div>` : "";
    const organization = vcard.organization ? `<div class="vcard-subtitle">${escapeHtml(vcard.organization)}</div>` : "";
    const numbers = (vcard.numbers || [])
      .map((value) => {
        const normalizedHref = String(value).replace(/[^\d+]/g, "");
        return `<a class="vcard-number" href="tel:${escapeHtml(normalizedHref)}">${escapeHtml(value)}</a>`;
      })
      .join("");
    const emails = (vcard.emails || [])
      .map((value) => `<a class="vcard-email" href="mailto:${escapeHtml(value)}">${escapeHtml(value)}</a>`)
      .join("");
    return `
      <div class="vcard-message">
        <div class="vcard-label">Contact card</div>
        <div class="vcard-name">${name}</div>
        ${title}
        ${organization}
        ${numbers}
        ${emails}
      </div>
    `;
  };

  const renderCallEvent = (callEvent) => {
    if (!callEvent) {
      return "";
    }
    const label = escapeHtml(callEvent.label || "Voice call");
    return `<div class="message-placeholder is-call">${label}</div>`;
  };

  const renderPollEvent = (pollEvent) => {
    if (!pollEvent) {
      return "";
    }
    const title = escapeHtml(pollEvent.title || "Poll");
    return `<div class="message-placeholder is-poll">Poll: ${title}</div>`;
  };

  const renderReplyPreview = (replyTo) => {
    if (!replyTo) {
      return "";
    }
    const senderName = escapeHtml(replyTo.sender_name || "Unknown");
    const replyText = replyTo.text
      ? formatMessageText(replyTo.text, replyTo.mentions || [])
      : '<span class="reply-text-muted">Message</span>';
    const sideClass = replyTo.is_from_me ? "is-from-me" : "";
    return `
      <div class="reply-preview ${sideClass}">
        <div class="reply-sender">${senderName}</div>
        <div class="reply-text">${replyText}</div>
      </div>
    `;
  };

  const placeholderForMessage = (message) => {
    if (message.text || message.media || message.vcard || message.call_event || message.poll_event) {
      return "";
    }
    if (message.message_type === 59) {
      return '<div class="message-placeholder is-deleted">This message was deleted.</div>';
    }
    if (message.message_type === 14) {
      return '<div class="message-placeholder is-call">Voice call</div>';
    }
    if (message.message_type === 46) {
      return '<div class="message-placeholder is-poll">Poll</div>';
    }
    return '<div class="message-placeholder">Unsupported message.</div>';
  };

  const renderMessages = () => {
    const chat = selectedChat();
    chatTitleNode.textContent = chat ? chat.chat_name : "Select a chat";
    if (chat && chatHeaderAvatarNode) {
      renderAvatarNode(chatHeaderAvatarNode, chat, chat.chat_name);
    } else if (chatHeaderAvatarNode) {
      chatHeaderAvatarNode.innerHTML = "?";
      chatHeaderAvatarNode.style.background = "";
    }

    if (!state.messages.length) {
      messagesNode.innerHTML = '<div class="empty-state">No messages to display.</div>';
      return;
    }

    const rows = [...state.messages].reverse();
    messagesNode.innerHTML = rows
      .map((message) => {
        const directionClass = message.is_from_me ? "outgoing" : "incoming";
        const sender = message.sender_name || (chat ? chat.chat_name : "Unknown");
        const senderKey = String(message.sender_key || sender || "");
        const senderStyle =
          chat && chat.is_group && !message.is_from_me && senderKey
            ? ` style="color:${escapeHtml(senderColorFromKey(senderKey))}"`
            : "";
        const text = message.text
          ? `<div class="message-text">${formatMessageText(message.text, message.mentions || [])}</div>`
          : "";
        const reply = renderReplyPreview(message.reply_to);
        const media = renderMedia(message.media);
        const vcard = renderVCard(message.vcard);
        const callEvent = renderCallEvent(message.call_event);
        const pollEvent = renderPollEvent(message.poll_event);
        const placeholder = placeholderForMessage(message);

        return `
          <article class="message ${directionClass}">
            <div class="sender"${senderStyle}>${escapeHtml(sender)}</div>
            ${reply}
            ${text}
            ${media}
            ${vcard}
            ${callEvent}
            ${pollEvent}
            ${placeholder}
            <div class="message-meta">${escapeHtml(formatDate(message.message_date))}</div>
          </article>
        `;
      })
      .join("");
  };

  const scrollMessagesToBottom = ({ watchMedia = false } = {}) => {
    const applyBottom = () => {
      messagesNode.scrollTop = messagesNode.scrollHeight;
    };

    applyBottom();
    window.requestAnimationFrame(() => {
      applyBottom();
      window.requestAnimationFrame(applyBottom);
    });

    if (!watchMedia) {
      return;
    }

    messagesNode.querySelectorAll("img, video").forEach((mediaNode) => {
      if (mediaNode.dataset.bottomSyncBound === "1") {
        return;
      }
      mediaNode.dataset.bottomSyncBound = "1";
      const syncBottom = () => {
        window.requestAnimationFrame(applyBottom);
      };
      mediaNode.addEventListener("load", syncBottom, { once: true });
      mediaNode.addEventListener("loadeddata", syncBottom, { once: true });
      mediaNode.addEventListener("error", syncBottom, { once: true });
    });
  };

  const setInfoView = (viewName) => {
    const infoSelected = viewName === "info";
    infoViewInfo.classList.toggle("hidden", !infoSelected);
    infoViewMembers.classList.toggle("hidden", infoSelected);
    infoMain?.classList.toggle("is-members-view", !infoSelected);
    groupInfoNav.querySelectorAll(".info-nav-btn").forEach((button) => {
      button.classList.toggle("is-active", button.dataset.infoView === viewName);
    });
  };

  const fetchChats = async ({ reset = true } = {}) => {
    if (state.loadingChats) {
      return;
    }
    state.loadingChats = true;
    if (reset) {
      state.chatOffset = 0;
      state.hasMoreChats = true;
    }

    const params = new URLSearchParams({
      tab: state.tab,
      limit: String(state.chatPageSize),
      offset: String(state.chatOffset),
    });
    if (state.query) {
      params.set("q", state.query);
    }
    const response = await fetch(`/api/chats?${params.toString()}`);
    if (!response.ok) {
      state.loadingChats = false;
      return;
    }
    const payload = await response.json();
    const incomingChats = payload.chats || [];
    state.chats = reset ? incomingChats : [...state.chats, ...incomingChats];
    state.chatOffset = state.chats.length;
    state.hasMoreChats = incomingChats.length === state.chatPageSize;
    state.counts = payload.counts || state.counts;

    if (!state.chats.find((chat) => chat.chat_id === state.selectedChatId)) {
      state.selectedChatId = state.chats.length ? state.chats[0].chat_id : null;
      await fetchMessages({ replaceCurrent: true, preservePosition: false });
    }

    setTabCounts();
    syncTabUI();
    renderChats();
    updateUrl();
    state.loadingChats = false;
  };

  const fetchMessages = async ({ replaceCurrent, preservePosition }) => {
    const selectedChatId = state.selectedChatId;
    if (!selectedChatId) {
      state.messages = [];
      state.nextBefore = null;
      renderMessages();
      return;
    }
    if (!replaceCurrent && (!state.nextBefore || state.loadingOlder)) {
      return;
    }

    const requestToken = state.messageRequestToken + 1;
    state.messageRequestToken = requestToken;

    const previousHeight = messagesNode.scrollHeight;
    const previousTop = messagesNode.scrollTop;
    if (!replaceCurrent) {
      state.loadingOlder = true;
    }

    const params = new URLSearchParams({ limit: "100" });
    if (!replaceCurrent && state.nextBefore) {
      params.set("before", state.nextBefore);
    }

    try {
      const response = await fetch(`/api/chats/${selectedChatId}/messages?${params.toString()}`);
      if (!response.ok) {
        return;
      }

      const payload = await response.json();
      if (requestToken !== state.messageRequestToken || selectedChatId !== state.selectedChatId) {
        return;
      }

      if (replaceCurrent) {
        state.messages = payload.messages || [];
      } else {
        state.messages = [...state.messages, ...(payload.messages || [])];
      }
      state.nextBefore = payload.next_before || null;
      renderMessages();
      renderChats();
      updateUrl();

      if (replaceCurrent) {
        scrollMessagesToBottom({ watchMedia: true });
      } else if (preservePosition) {
        const newHeight = messagesNode.scrollHeight;
        messagesNode.scrollTop = newHeight - previousHeight + previousTop;
      }

      openMobileChatPanel();
    } finally {
      if (!replaceCurrent) {
        state.loadingOlder = false;
      }
    }
  };

  const closeInfoModal = () => {
    if (document.activeElement instanceof HTMLElement && infoModal.contains(document.activeElement)) {
      chatContactButton?.focus();
    }
    infoModal.classList.add("hidden");
    infoModal.setAttribute("aria-hidden", "true");
  };

  const openImageViewer = (imageUrl, imageName) => {
    imageViewerImage.src = imageUrl;
    imageViewerImage.alt = imageName || "Message image";
    imageViewerCaption.textContent = imageName || "";
    imageViewerModal.classList.remove("hidden");
    imageViewerModal.setAttribute("aria-hidden", "false");
    imageViewerCloseButton.focus();
  };

  const closeImageViewer = () => {
    if (document.activeElement instanceof HTMLElement && imageViewerModal.contains(document.activeElement)) {
      chatContactButton?.focus({ preventScroll: true });
    }
    imageViewerModal.classList.add("hidden");
    imageViewerModal.setAttribute("aria-hidden", "true");
    imageViewerImage.src = "";
  };

  const renderInfoModal = (info) => {
    infoTitle.textContent = info.chat_name || "Chat";
    infoTagline.textContent = info.is_group ? "Group chat" : "Direct chat";
    const numberText = info.is_group ? "" : info.contact_number || "";
    infoNumber.textContent = numberText;
    infoNumber.classList.toggle("hidden", !numberText);
    infoType.textContent = info.is_group ? "Group" : "Direct";
    infoUnread.textContent = String(info.unread_count || 0);
    infoArchived.textContent = info.is_archived ? "Yes" : "No";
    infoMuted.textContent = info.muted_until ? formatDate(info.muted_until) : "Not muted";
    const infoModalContent = infoModal.querySelector(".info-modal-content");
    infoModalContent?.classList.toggle("is-direct", !info.is_group);

    const titleForAvatar = info.chat_name || info.contact_jid || "Chat";
    renderAvatarNode(infoAvatar, info, titleForAvatar);

    if (!info.group) {
      groupInfoNav.classList.add("hidden");
      groupSection.classList.add("hidden");
      groupMembers.innerHTML = "";
      groupMemberCountSummary.textContent = "";
      setInfoView("info");
      return;
    }

    groupInfoNav.classList.remove("hidden");
    groupSection.classList.remove("hidden");
    groupCreator.textContent = info.group.creator_jid || "Unknown";
    groupOwner.textContent = info.group.owner_jid || "Unknown";
    groupMemberCount.textContent = String(info.group.member_count || 0);
    groupMemberCountSummary.textContent = `${String(info.group.member_count || 0)} members`;
    groupMembers.innerHTML = (info.group.members || [])
      .map((member) => {
        const admin = member.is_admin ? "Admin" : "";
        const phone = memberPhoneLabel(member);
        return `
          <li class="group-member-row">
            <div class="group-member-main">
              ${memberAvatarMarkup(member, "avatar-sm")}
              <div>
                <div class="group-member-name">${escapeHtml(member.name || "Unknown")}</div>
                ${phone ? `<div class="member-phone">${escapeHtml(phone)}</div>` : ""}
              </div>
            </div>
            <div class="group-member-right">
              <span class="group-member-role">${escapeHtml(admin)}</span>
              <span class="group-member-chevron">›</span>
            </div>
          </li>
        `;
      })
      .join("");
    setInfoView("members");
  };

  const openInfoModal = async () => {
    if (!state.selectedChatId) {
      return;
    }
    const cacheKey = String(state.selectedChatId);
    if (!state.infoCache[cacheKey]) {
      const response = await fetch(`/api/chats/${state.selectedChatId}/info`);
      if (!response.ok) {
        return;
      }
      state.infoCache[cacheKey] = await response.json();
    }
    renderInfoModal(state.infoCache[cacheKey]);
    infoModal.classList.remove("hidden");
    infoModal.setAttribute("aria-hidden", "false");
    infoCloseButton.focus();
  };

  const setupResizer = () => {
    const storedWidth = Number.parseInt(window.localStorage.getItem(SIDEBAR_WIDTH_KEY) || "", 10);
    if (!Number.isNaN(storedWidth)) {
      document.documentElement.style.setProperty("--sidebar-width", `${clamp(storedWidth, 280, 640)}px`);
    }

    sidebarResizer.addEventListener("pointerdown", (event) => {
      if (window.innerWidth <= 980) {
        return;
      }
      event.preventDefault();
      document.body.classList.add("is-resizing");

      const onMove = (moveEvent) => {
        const maxWidth = Math.max(420, window.innerWidth - 320);
        const nextWidth = clamp(moveEvent.clientX, 280, Math.min(640, maxWidth));
        document.documentElement.style.setProperty("--sidebar-width", `${nextWidth}px`);
      };

      const onUp = () => {
        document.body.classList.remove("is-resizing");
        const computedWidth = Number.parseInt(
          getComputedStyle(document.documentElement).getPropertyValue("--sidebar-width"),
          10
        );
        if (!Number.isNaN(computedWidth)) {
          window.localStorage.setItem(SIDEBAR_WIDTH_KEY, String(computedWidth));
        }
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onUp);
      };

      window.addEventListener("pointermove", onMove);
      window.addEventListener("pointerup", onUp);
    });
  };

  tabsContainer.addEventListener("click", async (event) => {
    const target = event.target.closest(".tab");
    if (!target) {
      return;
    }
    const nextTab = target.dataset.tab;
    if (!nextTab || nextTab === state.tab) {
      return;
    }
    state.tab = nextTab;
    state.selectedChatId = null;
    state.messages = [];
    state.nextBefore = null;
    closeMobileChatPanel();
    await fetchChats({ reset: true });
  });

  chatListNode.addEventListener("click", async (event) => {
    const target = event.target.closest(".chat-row");
    if (!target) {
      return;
    }
    const chatId = Number.parseInt(target.dataset.chatId || "", 10);
    if (Number.isNaN(chatId)) {
      return;
    }
    if (chatId === state.selectedChatId) {
      openMobileChatPanel();
      return;
    }
    state.selectedChatId = chatId;
    await fetchMessages({ replaceCurrent: true, preservePosition: false });
  });

  messagesNode.addEventListener("scroll", async () => {
    if (messagesNode.scrollTop > 80 || !state.nextBefore || state.loadingOlder) {
      return;
    }
    await fetchMessages({ replaceCurrent: false, preservePosition: true });
  });

  messagesNode.addEventListener("click", (event) => {
    const target = event.target.closest(".media-image-trigger");
    if (!target) {
      return;
    }
    const imageUrl = target.dataset.imageUrl || "";
    if (!imageUrl) {
      return;
    }
    openImageViewer(imageUrl, target.dataset.imageName || "");
  });

  chatListNode.addEventListener("scroll", async () => {
    if (!state.hasMoreChats || state.loadingChats) {
      return;
    }
    const threshold = 120;
    const distanceFromBottom = chatListNode.scrollHeight - chatListNode.scrollTop - chatListNode.clientHeight;
    if (distanceFromBottom <= threshold) {
      await fetchChats({ reset: false });
    }
  });

  chatContactButton.addEventListener("click", openInfoModal);
  chatBackButton?.addEventListener("click", closeMobileChatPanel);
  groupInfoNav.addEventListener("click", (event) => {
    const target = event.target.closest(".info-nav-btn");
    if (!target) {
      return;
    }
    const viewName = target.dataset.infoView;
    if (!viewName) {
      return;
    }
    setInfoView(viewName);
  });
  infoCloseButton.addEventListener("click", closeInfoModal);
  imageViewerCloseButton.addEventListener("click", closeImageViewer);
  infoModal.addEventListener("click", (event) => {
    const target = event.target;
    if (target instanceof HTMLElement && target.dataset.closeModal === "true") {
      closeInfoModal();
    }
  });
  imageViewerModal.addEventListener("click", (event) => {
    const target = event.target;
    if (target instanceof HTMLElement && target.dataset.closeImageViewer === "true") {
      closeImageViewer();
    }
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeInfoModal();
      closeImageViewer();
    }
  });

  let searchTimer = null;
  searchInput.addEventListener("input", () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(async () => {
      state.query = searchInput.value.trim();
      await fetchChats({ reset: true });
    }, 220);
  });

  syncThemeListener();
  setupResizer();
  setTabCounts();
  syncTabUI();
  renderChats();
  renderMessages();
  if (state.selectedChatId) {
    scrollMessagesToBottom({ watchMedia: true });
    openMobileChatPanel();
  }
  updateUrl();
})();
