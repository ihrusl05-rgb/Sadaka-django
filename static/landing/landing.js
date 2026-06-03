function bindAmountControls(root) {
  const amountInput = root.querySelector("[data-amount-input]") || root.querySelector("#id_amount");
  const amountButtons = root.querySelectorAll("[data-amount]");

  if (!amountInput || !amountButtons.length) {
    return;
  }

  function setActiveButton(value) {
    const normalizedValue = Number(value || 0);
    let hasMatch = false;

    amountButtons.forEach((button) => {
      const isMatch = Number(button.dataset.amount || 0) === normalizedValue && normalizedValue > 0;
      button.classList.toggle("active", isMatch);
      hasMatch = hasMatch || isMatch;
    });

    if (!hasMatch && !amountInput.value) {
      const firstButton = amountButtons[0];
      if (firstButton) {
        firstButton.classList.add("active");
      }
    }
  }

  amountButtons.forEach((button) => {
    button.addEventListener("click", () => {
      amountInput.value = button.dataset.amount || "";
      setActiveButton(amountInput.value);
    });
  });

  amountInput.addEventListener("input", () => setActiveButton(amountInput.value));
  setActiveButton(amountInput.value);
}

function bindModeControls(root) {
  const modeInput = root.querySelector("[data-mode-input]") || root.querySelector("#id_mode");
  const modeButtons = root.querySelectorAll("[data-mode]");

  modeButtons.forEach((button) => {
    button.addEventListener("click", () => {
      modeButtons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      if (modeInput) {
        modeInput.value = button.dataset.mode || "once";
      }
    });
  });
}

function bindPaymentControls(root) {
  const paymentInput = root.querySelector("#id_payment_method");
  const paymentButtons = root.querySelectorAll("[data-payment-method]");
  if (!paymentInput || !paymentButtons.length) {
    return;
  }

  paymentButtons.forEach((button) => {
    button.addEventListener("click", () => {
      paymentButtons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      paymentInput.value = button.dataset.paymentMethod || "card";
    });
  });
}

function bindAnonymousSupportControls(root) {
  const anonymousInput = root.querySelector("#id_is_public_anonymous");
  const fullNameInput = root.querySelector("#id_full_name");
  const emailInput = root.querySelector("#id_email");
  const isAuthenticated = root.dataset.authenticated === "true";

  if (!anonymousInput || !fullNameInput || !emailInput) {
    return;
  }

  function syncRequiredState() {
    const isAnonymous = anonymousInput.checked;
    fullNameInput.required = !isAnonymous && !isAuthenticated;
    emailInput.required = false;
  }

  anonymousInput.addEventListener("change", syncRequiredState);
  syncRequiredState();
}

function syncSupportTargetCards(root) {
  root.querySelectorAll(".support-target-card").forEach((card) => {
    const input = card.querySelector('input[type="radio"]');
    card.classList.toggle("is-active", Boolean(input?.checked));
  });
}

function bindSupportTargetControls(root) {
  const targetInputs = root.querySelectorAll('.support-target-card input[type="radio"]');
  if (!targetInputs.length) {
    return;
  }

  targetInputs.forEach((input) => {
    input.addEventListener("change", () => syncSupportTargetCards(root));
  });
  syncSupportTargetCards(root);
}

function bindSupportModal(modal) {
  const closeControls = modal.querySelectorAll("[data-close-support-modal]");
  const triggers = document.querySelectorAll("[data-open-support-modal]");
  const amountInput = modal.querySelector("[data-amount-input]") || modal.querySelector("#id_amount");
  const modeInput = modal.querySelector("[data-mode-input]") || modal.querySelector("#id_mode");
  const projectInputs = modal.querySelectorAll('input[name="project"]');

  if (!closeControls.length) {
    return;
  }

  const openModal = () => {
    modal.hidden = false;
    document.body.classList.add("is-locked");
  };

  const closeModal = () => {
    modal.hidden = true;
    document.body.classList.remove("is-locked");
  };

  const setMode = (mode) => {
    if (!modeInput || !mode) {
      return;
    }
    modeInput.value = mode;
    modal.querySelectorAll("[data-mode]").forEach((button) => {
      button.classList.toggle("active", button.dataset.mode === mode);
    });
  };

  const setAmount = (amount) => {
    if (!amountInput || !amount) {
      return;
    }
    amountInput.value = amount;
    amountInput.dispatchEvent(new Event("input", { bubbles: true }));
  };

  const setProject = (projectId) => {
    if (!projectInputs.length) {
      return;
    }

    const normalizedValue = String(projectId || "");
    projectInputs.forEach((input) => {
      input.checked = input.value === normalizedValue;
    });
    syncSupportTargetCards(modal);
  };

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      setMode(trigger.dataset.supportMode || null);
      setAmount(trigger.dataset.supportAmount || null);
      setProject(trigger.dataset.supportProject || "");
      openModal();
    });
  });

  closeControls.forEach((control) => {
    control.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });

  if (modal.dataset.openOnLoad === "true") {
    openModal();
  }
}

function bindBasicModal(modal, { triggerSelector, closeSelector }) {
  const triggers = document.querySelectorAll(triggerSelector);
  const closeControls = modal.querySelectorAll(closeSelector);

  if (!modal || !triggers.length || !closeControls.length) {
    return;
  }

  const openModal = () => {
    modal.hidden = false;
    document.body.classList.add("is-locked");
  };

  const closeModal = () => {
    modal.hidden = true;
    document.body.classList.remove("is-locked");
  };

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", (event) => {
      event.preventDefault();
      openModal();
    });
  });

  closeControls.forEach((control) => {
    control.addEventListener("click", closeModal);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });
}

function bindExpandableText(root) {
  const content = root.querySelector("[data-expandable-text]");
  const toggle = root.querySelector("[data-expandable-toggle]");

  if (!content || !toggle) {
    return;
  }

  const collapsedClass = "is-collapsed";

  const syncVisibility = () => {
    toggle.hidden = content.scrollHeight <= content.clientHeight + 4;
  };

  toggle.addEventListener("click", () => {
    const isCollapsed = content.classList.contains(collapsedClass);
    content.classList.toggle(collapsedClass, !isCollapsed);
    toggle.textContent = isCollapsed ? "Скрыть описание" : "Полное описание";
  });

  window.requestAnimationFrame(syncVisibility);
  window.addEventListener("resize", syncVisibility);
}

function bindExpandableList(root) {
  const list = root.querySelector("[data-expandable-list]");
  const toggle = root.querySelector("[data-expandable-list-toggle]");

  if (!list || !toggle) {
    return;
  }

  const hiddenItems = Array.from(list.querySelectorAll(".is-hidden"));

  if (!hiddenItems.length) {
    toggle.hidden = true;
    return;
  }

  let expanded = false;

  toggle.addEventListener("click", () => {
    expanded = !expanded;
    hiddenItems.forEach((item) => {
      item.hidden = !expanded;
    });
    toggle.textContent = expanded ? "Скрыть поступления" : "Показать все поступления";
  });
}

function parseJsonScript(id) {
  const node = document.getElementById(id);
  if (!node) {
    return [];
  }

  try {
    return JSON.parse(node.textContent);
  } catch (error) {
    return [];
  }
}

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderCityMosques(container, mosques, emptyMessage) {
  if (!container) {
    return;
  }

  if (!mosques.length) {
    container.innerHTML = `<div class="city-mosques-hint">${escapeHtml(emptyMessage)}</div>`;
    return;
  }

  container.innerHTML = mosques
    .map((mosque) => {
      const location = mosque.address || mosque.city || "";
      const thumbStyle = mosque.cover_image_url
        ? ` style="background-image: url('${escapeHtml(mosque.cover_image_url)}');"`
        : "";
      const detailUrl = mosque.detail_url || `/mosques/${encodeURIComponent(mosque.slug)}/`;
      return `
        <a class="city-mosque-card" href="${escapeHtml(detailUrl)}">
          <span class="city-mosque-thumb"${thumbStyle}></span>
          <span class="city-mosque-body">
            <strong>${escapeHtml(mosque.name)}</strong>
            <span class="city-mosque-meta">${escapeHtml(location)}</span>
          </span>
          <span class="city-mosque-open">Помочь</span>
        </a>
      `;
    })
    .join("");
}

function bindMosqueSearchForm(form) {
  const citySelect = form.querySelector("[data-city-select]");
  const queryInput = form.querySelector("[data-mosque-query]");
  const submitButton = form.querySelector('button[type="submit"]');
  const cityMosquesBlock = document.querySelector("[data-city-mosques-block]");
  const cityMosquesGrid = document.querySelector("[data-city-mosques-grid]");
  const cityMosquesBadge = document.querySelector("[data-city-mosques-badge]");

  if (!citySelect || !queryInput || !submitButton || !cityMosquesBlock || !cityMosquesGrid || !cityMosquesBadge) {
    return;
  }

  const searchableMosques = parseJsonScript("searchable-mosques-data");
  const rankedMosques = [...searchableMosques].sort((left, right) => {
    const collectedDiff = Number(right.collected_total || 0) - Number(left.collected_total || 0);
    if (collectedDiff !== 0) {
      return collectedDiff;
    }
    return String(left.name || "").localeCompare(String(right.name || ""), "ru");
  });

  function hideResults() {
    cityMosquesBlock.hidden = true;
  }

  function showResults() {
    cityMosquesBlock.hidden = false;
  }

  function getCityMosques(city) {
    const normalizedCity = normalizeText(city);
    return rankedMosques.filter((mosque) => normalizeText(mosque.city) === normalizedCity);
  }

  function filterCityMosques(cityMosques) {
    const normalizedQuery = normalizeText(queryInput.value);
    if (!normalizedQuery) {
      return cityMosques;
    }

    return cityMosques.filter((mosque) => {
      const haystack = normalizeText(`${mosque.name} ${mosque.address}`);
      return haystack.includes(normalizedQuery);
    });
  }

  function syncSubmitState() {
    submitButton.disabled = !searchableMosques.length || !citySelect.value;
    queryInput.disabled = !searchableMosques.length || !citySelect.value;
    if (!citySelect.value) {
      queryInput.value = "";
    }
  }

  function renderSearchResults() {
    const selectedCity = citySelect.value;
    const cityMosques = selectedCity ? getCityMosques(selectedCity) : [];
    const filteredMosques = filterCityMosques(cityMosques);

    if (!searchableMosques.length) {
      submitButton.disabled = true;
      cityMosquesBadge.textContent = "Нет мечетей";
      renderCityMosques(cityMosquesGrid, [], "Доступных мечетей пока нет. Загляните позже.");
      showResults();
      return;
    }

    if (!selectedCity) {
      submitButton.disabled = true;
      cityMosquesBadge.textContent = "Город не выбран";
      renderCityMosques(cityMosquesGrid, [], "Выберите город, чтобы увидеть мечети.");
      hideResults();
      return;
    }

    cityMosquesBadge.textContent = selectedCity;

    if (!cityMosques.length) {
      renderCityMosques(cityMosquesGrid, [], "В выбранном городе пока нет публичных мечетей.");
      showResults();
      return;
    }

    if (!filteredMosques.length) {
      renderCityMosques(
        cityMosquesGrid,
        [],
        "По вашему запросу мечети не найдены. Попробуйте изменить город или сократить запрос."
      );
      showResults();
      return;
    }

    renderCityMosques(
      cityMosquesGrid,
      filteredMosques,
      "По вашему запросу мечети не найдены. Попробуйте изменить город или сократить запрос."
    );
    showResults();
  }

  citySelect.addEventListener("change", () => {
    syncSubmitState();
    renderSearchResults();
  });

  queryInput.addEventListener("input", () => {
    if (!citySelect.value) {
      hideResults();
      return;
    }
    renderSearchResults();
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (!citySelect.value) {
      syncSubmitState();
      return;
    }
    renderSearchResults();
  });

  syncSubmitState();
}

function pluralizeMosques(count) {
  const normalized = Math.abs(Number(count) || 0);
  const mod10 = normalized % 10;
  const mod100 = normalized % 100;

  if (mod10 === 1 && mod100 !== 11) {
    return "мечеть";
  }
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return "мечети";
  }
  return "мечетей";
}

function bindMosqueCatalogSearch(root) {
  const citySelect = root.querySelector("[data-catalog-city-filter]");
  const queryInput = root.querySelector("[data-catalog-query]");
  const cards = Array.from(root.querySelectorAll("[data-mosque-card]"));
  const grid = root.querySelector("[data-mosque-catalog-grid]");
  const countNode = root.querySelector("[data-mosque-count]");
  const summaryNode = root.querySelector("[data-mosque-summary]");
  const emptyShell = root.querySelector("[data-mosque-empty-shell]");

  if (!citySelect || !queryInput || !cards.length || !grid || !countNode || !summaryNode || !emptyShell) {
    return;
  }

  function syncSummary(visibleCount, selectedCity, query) {
    countNode.textContent = `Найдено ${visibleCount} ${pluralizeMosques(visibleCount)}`;

    if (visibleCount === 0) {
      summaryNode.textContent = "Попробуйте изменить город или уточнить название мечети.";
      return;
    }

    if (selectedCity && query) {
      summaryNode.textContent = `Показаны мечети по запросу «${query}» в городе ${selectedCity}.`;
      return;
    }

    if (selectedCity) {
      summaryNode.textContent = `Показаны все доступные мечети в городе ${selectedCity}.`;
      return;
    }

    if (query) {
      summaryNode.textContent = `Показаны мечети по запросу «${query}».`;
      return;
    }

    summaryNode.textContent = "Откройте публичную страницу мечети, посмотрите активные проекты, реквизиты и поддержите нужный сбор.";
  }

  function applyFilters() {
    const selectedCity = normalizeText(citySelect.value);
    const rawCityValue = citySelect.value.trim();
    const query = normalizeText(queryInput.value);
    const hasActiveFilters = Boolean(selectedCity || query);

    let visibleCount = 0;

    cards.forEach((card) => {
      const city = normalizeText(card.dataset.mosqueCity);
      const haystack = normalizeText([
        card.dataset.mosqueName,
        card.dataset.mosqueCity,
        card.dataset.mosqueAddress,
        card.dataset.mosqueDescription,
      ].join(" "));

      const matchesCity = !selectedCity || city === selectedCity;
      const matchesQuery = !query || haystack.includes(query);
      const isVisible = matchesCity && matchesQuery;

      card.hidden = !isVisible;
      if (isVisible) {
        visibleCount += 1;
      }
    });

    grid.hidden = visibleCount === 0;
    emptyShell.hidden = visibleCount !== 0 || !hasActiveFilters;
    syncSummary(visibleCount, rawCityValue, queryInput.value.trim());
  }

  citySelect.addEventListener("change", applyFilters);
  queryInput.addEventListener("input", applyFilters);
  applyFilters();
}

function bindFaq(root) {
  const filterButtons = Array.from(root.querySelectorAll("[data-faq-filter]"));
  const faqItems = Array.from(root.querySelectorAll("[data-faq-item]"));
  const animationDuration = 220;

  if (!filterButtons.length || !faqItems.length) {
    return;
  }

  function closeItem(item) {
    const question = item.querySelector("[data-faq-toggle]");
    const panel = item.querySelector("[data-faq-panel]");
    if (!question || !panel) {
      return;
    }

    question.setAttribute("aria-expanded", "false");
    panel.classList.remove("is-open");
    window.setTimeout(() => {
      if (!panel.classList.contains("is-open")) {
        panel.hidden = true;
      }
    }, animationDuration);
  }

  function openItem(item) {
    const question = item.querySelector("[data-faq-toggle]");
    const panel = item.querySelector("[data-faq-panel]");
    if (!question || !panel) {
      return;
    }

    faqItems.forEach((otherItem) => {
      if (otherItem !== item) {
        closeItem(otherItem);
      }
    });

    panel.hidden = false;
    window.requestAnimationFrame(() => {
      question.setAttribute("aria-expanded", "true");
      panel.classList.add("is-open");
    });
  }

  function applyFilter(nextCategory) {
    filterButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.faqFilter === nextCategory);
    });

    faqItems.forEach((item) => {
      const categories = (item.dataset.faqCategories || "").split(/\s+/).filter(Boolean);
      const isVisible = nextCategory === "all" || categories.includes(nextCategory);
      item.hidden = !isVisible;
      if (!isVisible) {
        closeItem(item);
      }
    });
  }

  filterButtons.forEach((button) => {
    button.addEventListener("click", () => applyFilter(button.dataset.faqFilter || "all"));
  });

  faqItems.forEach((item) => {
    const question = item.querySelector("[data-faq-toggle]");
    const panel = item.querySelector("[data-faq-panel]");
    if (!question || !panel) {
      return;
    }

    question.addEventListener("click", () => {
      const isExpanded = question.getAttribute("aria-expanded") === "true";
      if (isExpanded) {
        closeItem(item);
        return;
      }
      openItem(item);
    });
  });

  applyFilter("all");
}

function setButtonLoading(button) {
  if (!button) {
    return;
  }

  button.disabled = true;
  button.classList.add("is-loading");
  const label = button.querySelector("span");
  if (label) {
    label.textContent = "Подождите...";
  } else {
    button.textContent = "Подождите...";
  }
}

function resetButtonLoading(button) {
  if (!button) {
    return;
  }

  button.disabled = false;
  button.classList.remove("is-loading");
  const label = button.querySelector("span");
  const nextLabel = button.dataset.submitLabel || button.dataset.defaultLabel;
  if (label && nextLabel) {
    label.textContent = nextLabel;
  } else if (nextLabel) {
    button.textContent = nextLabel;
  }
}

function bindFormLoading(form) {
  if (!form) {
    return;
  }

  form.addEventListener("submit", (event) => {
    const submitter = event.submitter;
    if (!submitter || submitter.disabled) {
      event.preventDefault();
      return;
    }
    setButtonLoading(submitter);
  });
}

function bindOtpInputs(root) {
  const hiddenInput = root.querySelector("[data-otp-value]");
  const slots = Array.from(root.querySelectorAll("[data-otp-slot]"));
  const submitButton = root.querySelector("[data-otp-submit]");

  if (!hiddenInput || !slots.length || !submitButton) {
    return;
  }

  const syncValue = () => {
    const value = slots.map((slot) => slot.value).join("");
    hiddenInput.value = value;
    submitButton.disabled = value.length !== slots.length;
  };

  const fillFromString = (value) => {
    const digits = String(value || "").replace(/\D/g, "").slice(0, slots.length).split("");
    slots.forEach((slot, index) => {
      slot.value = digits[index] || "";
    });
    syncValue();
    if (slots[0].offsetParent !== null) {
      const nextEmptySlot = slots.find((slot) => !slot.value);
      (nextEmptySlot || slots[slots.length - 1]).focus();
    }
  };

  slots.forEach((slot, index) => {
    slot.addEventListener("input", () => {
      slot.value = slot.value.replace(/\D/g, "").slice(-1);
      if (slot.value && index < slots.length - 1) {
        slots[index + 1].focus();
      }
      syncValue();
    });

    slot.addEventListener("keydown", (event) => {
      if (event.key === "Backspace" && !slot.value && index > 0) {
        slots[index - 1].focus();
      }
      if (event.key === "ArrowLeft" && index > 0) {
        event.preventDefault();
        slots[index - 1].focus();
      }
      if (event.key === "ArrowRight" && index < slots.length - 1) {
        event.preventDefault();
        slots[index + 1].focus();
      }
    });

    slot.addEventListener("paste", (event) => {
      event.preventDefault();
      fillFromString(event.clipboardData.getData("text"));
    });
  });

  if (hiddenInput.value) {
    fillFromString(hiddenInput.value);
  } else {
    syncValue();
    if (slots[0].offsetParent !== null) {
      slots[0].focus();
    }
  }
}

function setAuthPanel(root, nextPanel) {
  root.querySelectorAll("[data-auth-panel]").forEach((panel) => {
    panel.classList.toggle("is-hidden", panel.dataset.authPanel !== nextPanel);
  });
  root.dataset.authStep = nextPanel;

  if (nextPanel === "enter_code") {
    const firstSlot = root.querySelector("[data-otp-slot]");
    if (firstSlot) {
      window.requestAnimationFrame(() => firstSlot.focus());
    }
  }
}

function syncAuthDebugCode(root, debugCode) {
  const debugBlock = root.querySelector("[data-auth-debug]");
  const debugValue = root.querySelector("[data-auth-debug-value]");
  if (!debugBlock || !debugValue) {
    return;
  }

  const hasValue = Boolean(debugCode);
  debugBlock.classList.toggle("is-hidden", !hasValue);
  debugValue.textContent = debugCode || "";
}

function bindAuthStatusPolling(root) {
  const statusUrl = root.dataset.statusUrl;
  const statusText = root.querySelector("[data-auth-status-text]");
  const confirmedCopy = root.querySelector("[data-auth-confirmed-copy]");
  const providerStatusText = root.dataset.providerStatusText || "Ожидаем подтверждение…";
  const confirmedWithNameTemplate = root.dataset.providerConfirmedWithName || "Аккаунт {display_name} подтвержден.";
  const confirmedWithoutName = root.dataset.providerConfirmedWithoutName || "Аккаунт подтвержден.";

  if (!statusUrl || root.dataset.authStep !== "await_provider") {
    return;
  }

  let stopped = false;

  const stopPolling = () => {
    stopped = true;
  };

  const renderStatus = (payload) => {
    if (!payload || !payload.status) {
      return;
    }

    if (payload.status === "confirmed") {
      setAuthPanel(root, "enter_code");
      syncAuthDebugCode(root, payload.debug_code || "");
      if (confirmedCopy) {
        confirmedCopy.textContent = payload.display_name
          ? confirmedWithNameTemplate.replace("{display_name}", payload.display_name)
          : confirmedWithoutName;
      }
      stopPolling();
      return;
    }

    if (payload.status === "expired") {
      if (statusText) {
        statusText.textContent = "Сессия входа истекла. Начните заново.";
      }
      stopPolling();
      return;
    }

    if (statusText) {
      statusText.textContent = providerStatusText;
    }
  };

  const poll = async () => {
    if (stopped) {
      return;
    }

    try {
      const response = await fetch(statusUrl, {
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      if (!response.ok) {
        return;
      }
      const payload = await response.json();
      renderStatus(payload);
    } catch (error) {
      return;
    }

    if (!stopped) {
      window.setTimeout(poll, 2500);
    }
  };

  poll();
}

function bindAuthFlow(root) {
  root.querySelectorAll("[data-start-auth-form]").forEach((form) => bindAuthStartForm(root, form));
  bindOtpInputs(root);
  bindAuthStatusPolling(root);
  root.querySelectorAll("form").forEach((form) => bindFormLoading(form));

  const shouldAutoOpen = root.dataset.autoOpenAuth === "true";
  const authUrl = root.dataset.authUrl;
  if (shouldAutoOpen && authUrl && root.dataset.authStep === "await_provider") {
    window.setTimeout(() => {
      window.open(authUrl, "_blank", "noopener");
    }, 120);
  }
}

function bindAuthStartForm(root, form) {
  const submitButton = form.querySelector('button[type="submit"]');
  if (!submitButton || typeof window.fetch !== "function") {
    return;
  }

  if (submitButton.dataset.submitLabel) {
    submitButton.dataset.defaultLabel = submitButton.dataset.submitLabel;
  }

  const renderError = (message) => {
    let errorNode = root.querySelector(".auth-message");
    if (!errorNode) {
      errorNode = document.createElement("div");
      errorNode.className = "message error auth-message";
      errorNode.setAttribute("role", "alert");
      root.prepend(errorNode);
    }
    errorNode.textContent = message;
  };

  const clearError = () => {
    const errorNode = root.querySelector(".auth-message");
    if (errorNode) {
      errorNode.remove();
    }
  };

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearError();

    const popup = window.open("about:blank", "sadakaSocialAuth");
    if (popup) {
      try {
        popup.opener = null;
        popup.document.title = "Sadaka Auth";
      } catch (error) {
        // Ignore cross-origin/access timing issues on popup bootstrap.
      }
    }
    const formData = new FormData(form);
    const submitUrl = form.getAttribute("action") || window.location.href;

    try {
      const response = await fetch(submitUrl, {
        method: "POST",
        body: formData,
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.ok || !payload.auth_url) {
        if (popup && !popup.closed) {
          popup.close();
        }
        renderError(payload.error || "Не удалось открыть бота. Попробуйте ещё раз.");
        resetButtonLoading(submitButton);
        return;
      }

      if (popup && !popup.closed) {
        popup.location = payload.auth_url;
      } else {
        window.open(payload.auth_url, "_blank");
      }

      window.setTimeout(() => {
        window.location.href = payload.redirect_url || window.location.href;
      }, 120);
    } catch (error) {
      if (popup && !popup.closed) {
        popup.close();
      }
      resetButtonLoading(submitButton);
      form.submit();
    }
  });
}

function bindCopyControl(root) {
  const source = root.querySelector("[data-copy-source]");
  const button = root.querySelector("[data-copy-button]");
  const feedback = root.querySelector("[data-copy-feedback]");

  if (!source || !button) {
    return;
  }

  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(source.value);
      if (feedback) {
        feedback.textContent = "Ссылка скопирована.";
      }
    } catch (error) {
      source.focus();
      source.select();
      if (feedback) {
        feedback.textContent = "Не удалось скопировать автоматически. Скопируйте ссылку вручную.";
      }
    }
  });
}

function getCsrfToken() {
  const value = `; ${document.cookie}`;
  const parts = value.split("; csrftoken=");
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return "";
}

function setSiteCookie(name, value, days = 365) {
  const expires = new Date(Date.now() + days * 86400000).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
}

function getSiteCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) {
    return decodeURIComponent(parts.pop().split(";").shift() || "");
  }
  return "";
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function createNotificationSoundController() {
  const storageKeys = {
    enabled: "sadaka_notifications_sound_enabled",
    lastSeen: "sadaka_notifications_last_seen_count",
    unlocked: "sadaka_notifications_sound_unlocked",
    lastPlayedAt: "sadaka_notifications_last_played_at",
  };
  const cooldownMs = 10000;
  let audioContext = null;

  const isEnabled = () => localStorage.getItem(storageKeys.enabled) !== "false";
  const setEnabled = (enabled) => localStorage.setItem(storageKeys.enabled, enabled ? "true" : "false");
  const isUnlocked = () => localStorage.getItem(storageKeys.unlocked) === "true";
  const markUnlocked = () => localStorage.setItem(storageKeys.unlocked, "true");
  const getLastSeenCount = () => Number(localStorage.getItem(storageKeys.lastSeen) || "0");
  const setLastSeenCount = (count) => localStorage.setItem(storageKeys.lastSeen, String(Math.max(0, Number(count || 0))));
  const canPlayNow = () => {
    const lastPlayedAt = Number(localStorage.getItem(storageKeys.lastPlayedAt) || "0");
    return Date.now() - lastPlayedAt >= cooldownMs;
  };

  const unlock = async () => {
    if (isUnlocked()) {
      return;
    }
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        return;
      }
      audioContext = audioContext || new AudioContextClass();
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }
      markUnlocked();
    } catch (error) {
      console.warn("Sadaka notifications: unable to unlock sound", error);
    }
  };

  const play = async () => {
    if (!isEnabled() || !isUnlocked() || !canPlayNow()) {
      return;
    }
    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioContextClass) {
        return;
      }
      audioContext = audioContext || new AudioContextClass();
      if (audioContext.state === "suspended") {
        await audioContext.resume();
      }
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      oscillator.type = "sine";
      oscillator.frequency.setValueAtTime(740, audioContext.currentTime);
      gainNode.gain.setValueAtTime(0.0001, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.045, audioContext.currentTime + 0.03);
      gainNode.gain.exponentialRampToValueAtTime(0.0001, audioContext.currentTime + 0.2);
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.22);
      localStorage.setItem(storageKeys.lastPlayedAt, String(Date.now()));
    } catch (error) {
      console.warn("Sadaka notifications: unable to play sound", error);
    }
  };

  ["click", "touchstart", "keydown"].forEach((eventName) => {
    window.addEventListener(eventName, unlock, { once: true, passive: true });
  });

  return {
    isEnabled,
    setEnabled,
    getLastSeenCount,
    setLastSeenCount,
    play,
  };
}

function renderNotificationItems(items, { compact = false } = {}) {
  if (!Array.isArray(items) || !items.length) {
    return '<div class="notification-empty">Новых уведомлений нет</div>';
  }

  return items
    .map((item) => {
      const link = item.link || "";
      const actionLabel = link ? "Открыть" : "Прочитано";
      const actionTag = link
        ? `<a class="button ghost" href="${escapeHtml(link)}" data-notification-link data-notification-id="${item.id}">${actionLabel}</a>`
        : `<button class="button ghost" type="button" data-notification-read data-notification-id="${item.id}">${actionLabel}</button>`;
      const deleteTag = `<button class="button ghost danger" type="button" data-notification-delete data-notification-id="${item.id}">Удалить</button>`;
      return `
        <article class="notification-item notification-item--${escapeHtml(item.notification_type)}${item.is_read ? "" : " notification-item--unread"}" data-notification-id="${item.id}">
          <div class="notification-item-head">
            <strong>${escapeHtml(item.title)}</strong>
            <time datetime="${escapeHtml(item.created_at)}">${escapeHtml(item.created_label || "")}</time>
          </div>
          <p>${escapeHtml(item.message)}</p>
          <div class="notification-item-foot">
            <span>${escapeHtml(item.type_label || item.notification_type || "")}</span>
            <div class="notification-actions">${item.is_read && compact ? "" : actionTag}${deleteTag}</div>
          </div>
        </article>
      `;
    })
    .join("");
}

function bindNotifications(root, soundController) {
  const toggle = root.querySelector("[data-notifications-toggle]");
  const dropdown = root.querySelector("[data-notifications-dropdown]");
  const list = root.querySelector("[data-notifications-list]");
  const badge = root.querySelector("[data-notifications-badge]");
  const readAllButtons = root.querySelectorAll("[data-notifications-read-all]");
  const soundToggle = root.querySelector("[data-notifications-sound-toggle]");
  const listUrl = root.dataset.listUrl;
  const unreadUrl = root.dataset.unreadUrl;
  const readAllUrl = root.dataset.readAllUrl;

  if (!toggle || !dropdown || !list || !badge || !listUrl || !unreadUrl || !readAllUrl) {
    return;
  }

  let isOpen = false;
  let lastKnownCount = soundController.getLastSeenCount();

  const setBadge = (count) => {
    const normalized = Math.max(0, Number(count || 0));
    badge.hidden = normalized <= 0;
    badge.textContent = String(normalized);
  };

  const fetchUnreadCount = async ({ allowSound = false } = {}) => {
    try {
      const response = await fetch(unreadUrl, {
        headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      const count = Number(payload.count || 0);
      setBadge(count);
      if (allowSound && count > lastKnownCount) {
        await soundController.play();
      }
      if (isOpen) {
        soundController.setLastSeenCount(count);
      }
      lastKnownCount = count;
      return count;
    } catch (error) {
      console.warn("Sadaka notifications: unable to fetch unread count", error);
      return lastKnownCount;
    }
  };

  const fetchNotifications = async ({ filter = "all", limit = 8 } = {}) => {
    try {
      const url = new URL(listUrl, window.location.origin);
      url.searchParams.set("filter", filter);
      url.searchParams.set("limit", String(limit));
      const response = await fetch(url, {
        headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      list.innerHTML = renderNotificationItems(payload.results || [], { compact: true });
      return payload.results || [];
    } catch (error) {
      console.warn("Sadaka notifications: unable to fetch notifications", error);
      list.innerHTML = '<div class="notification-empty">Не удалось загрузить уведомления.</div>';
      return [];
    }
  };

  const openNotificationLink = (href) => {
    if (!href) {
      return;
    }
    window.location.assign(href);
  };

  const markNotificationRead = async (notificationId) => {
    try {
      const response = await fetch(`/api/notifications/${notificationId}/read/`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: "{}",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      await fetchUnreadCount();
      await fetchNotifications();
    } catch (error) {
      console.warn("Sadaka notifications: unable to mark notification as read", error);
    }
  };

  const deleteNotification = async (notificationId) => {
    try {
      const response = await fetch(`/api/notifications/${notificationId}/delete/`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: "{}",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      await fetchUnreadCount();
      await fetchNotifications();
    } catch (error) {
      console.warn("Sadaka notifications: unable to delete notification", error);
    }
  };

  const markAllNotificationsRead = async () => {
    try {
      const response = await fetch(readAllUrl, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: "{}",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      setBadge(0);
      soundController.setLastSeenCount(0);
      lastKnownCount = 0;
      await fetchNotifications();
    } catch (error) {
      console.warn("Sadaka notifications: unable to mark all notifications as read", error);
    }
  };

  const openDropdown = async () => {
    dropdown.hidden = false;
    root.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    isOpen = true;
    const count = await fetchUnreadCount();
    soundController.setLastSeenCount(count);
    await fetchNotifications();
  };

  const closeDropdown = () => {
    dropdown.hidden = true;
    root.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    isOpen = false;
  };

  toggle.addEventListener("click", async (event) => {
    event.preventDefault();
    if (isOpen) {
      closeDropdown();
      return;
    }
    await openDropdown();
  });

  document.addEventListener("click", (event) => {
    if (!root.contains(event.target) && isOpen) {
      closeDropdown();
    }
  });

  list.addEventListener("click", async (event) => {
    const readButton = event.target.closest("[data-notification-read]");
    const linkButton = event.target.closest("[data-notification-link]");
    const deleteButton = event.target.closest("[data-notification-delete]");
    if (readButton) {
      event.preventDefault();
      await markNotificationRead(readButton.dataset.notificationId);
      return;
    }
    if (deleteButton) {
      event.preventDefault();
      await deleteNotification(deleteButton.dataset.notificationId);
      return;
    }
    if (linkButton) {
      event.preventDefault();
      const notificationId = linkButton.dataset.notificationId;
      if (notificationId) {
        markNotificationRead(notificationId);
      }
      openNotificationLink(linkButton.getAttribute("href"));
    }
  });

  readAllButtons.forEach((button) => {
    button.addEventListener("click", (event) => {
      event.preventDefault();
      markAllNotificationsRead();
    });
  });

  if (soundToggle) {
    soundToggle.checked = soundController.isEnabled();
    soundToggle.addEventListener("change", () => {
      soundController.setEnabled(soundToggle.checked);
    });
  }

  fetchUnreadCount();
  window.setInterval(() => {
    fetchUnreadCount({ allowSound: true });
    if (isOpen) {
      fetchNotifications();
    }
  }, 30000);
}

function bindNotificationPage(root, soundController) {
  const list = root.querySelector("[data-notification-page-list]");
  const readAllButton = root.querySelector("[data-notifications-read-all]");
  const currentFilter = root.dataset.notificationPageFilter || "all";
  if (!list) {
    return;
  }

  const getSummaryValueNode = (key) => root.querySelector(`[data-notification-summary="${key}"] strong`);
  const emptyStateMessage = {
    all: "Уведомлений пока нет.",
    unread: "Непрочитанных уведомлений сейчас нет.",
    read: "Прочитанных уведомлений пока нет.",
    important: "Важных уведомлений сейчас нет.",
  };

  const updateSummaryCount = (key, delta) => {
    const node = getSummaryValueNode(key);
    if (!node) {
      return;
    }
    const current = Number(node.textContent || 0);
    node.textContent = String(Math.max(0, current + delta));
  };

  const ensureEmptyState = () => {
    const hasCards = list.querySelector("[data-notification-id]");
    let empty = list.querySelector("[data-notification-empty-state]");
    if (hasCards) {
      if (empty) {
        empty.remove();
      }
      return;
    }
    if (!empty) {
      empty = document.createElement("div");
      empty.className = "empty-card";
      empty.setAttribute("data-notification-empty-state", "");
      empty.textContent = emptyStateMessage[currentFilter] || emptyStateMessage.all;
      list.appendChild(empty);
    }
  };

  const openNotificationLink = (href) => {
    if (!href) {
      return;
    }
    window.location.assign(href);
  };

  const deleteNotification = async (notificationId) => {
    if (!notificationId) {
      return;
    }
    try {
      const response = await fetch(`/api/notifications/${notificationId}/delete/`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: "{}",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const card = list.querySelector(`[data-notification-id="${notificationId}"]`);
      if (card) {
        const wasUnread = card.classList.contains("notification-item--unread");
        card.remove();
        updateSummaryCount("total", -1);
        if (wasUnread) {
          updateSummaryCount("unread", -1);
        } else {
          updateSummaryCount("read", -1);
        }
        if (card.classList.contains("notification-item--warning") || card.classList.contains("notification-item--error")) {
          updateSummaryCount("important", -1);
        }
        ensureEmptyState();
      }
    } catch (error) {
      console.warn("Sadaka notifications: unable to delete notification from page", error);
    }
  };

  list.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-notification-read]");
    const link = event.target.closest("[data-notification-link]");
    const deleteButton = event.target.closest("[data-notification-delete]");
    const notificationId = (button || link || deleteButton)?.dataset.notificationId;
    if (!notificationId) {
      return;
    }
    if (deleteButton) {
      event.preventDefault();
      await deleteNotification(notificationId);
      return;
    }
    try {
      await fetch(`/api/notifications/${notificationId}/read/`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: "{}",
      });
      const card = list.querySelector(`[data-notification-id="${notificationId}"]`);
      if (card) {
        const wasUnread = card.classList.contains("notification-item--unread");
        card.classList.remove("notification-item--unread");
        const actionButton = card.querySelector("[data-notification-read]");
        if (actionButton) {
          actionButton.remove();
        }
        if (wasUnread) {
          updateSummaryCount("unread", -1);
          updateSummaryCount("read", 1);
        }
        if (currentFilter === "unread") {
          card.remove();
          ensureEmptyState();
        }
      }
      if (link) {
        openNotificationLink(link.getAttribute("href"));
      }
    } catch (error) {
      console.warn("Sadaka notifications: unable to mark notification from page", error);
      if (link) {
        openNotificationLink(link.getAttribute("href"));
      }
    }
  });

  if (readAllButton) {
    readAllButton.addEventListener("click", async () => {
      try {
        await fetch("/api/notifications/read-all/", {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
            "X-Requested-With": "XMLHttpRequest",
          },
          credentials: "same-origin",
          body: "{}",
        });
        const unreadCards = list.querySelectorAll(".notification-item--unread");
        const unreadCount = unreadCards.length;
        unreadCards.forEach((card) => card.classList.remove("notification-item--unread"));
        list.querySelectorAll("[data-notification-read]").forEach((button) => button.remove());
        if (unreadCount) {
          updateSummaryCount("read", unreadCount);
          updateSummaryCount("unread", -unreadCount);
        }
        if (currentFilter === "unread") {
          list.innerHTML = `<div class="empty-card" data-notification-empty-state>${emptyStateMessage.unread}</div>`;
        }
        soundController.setLastSeenCount(0);
      } catch (error) {
        console.warn("Sadaka notifications: unable to mark all notifications on page", error);
      }
    });
  }
}

function bindCookieBanner(root) {
  const acceptButton = root.querySelector("[data-cookie-accept]");
  const closeButton = root.querySelector("[data-cookie-close]");
  const consentValue = getSiteCookie("sadaka_cookie_consent");

  if (consentValue === "accepted") {
    root.hidden = true;
    return;
  }

  root.hidden = false;

  const closeBanner = () => {
    setSiteCookie("sadaka_cookie_consent", "accepted", 365);
    root.hidden = true;
  };

  acceptButton?.addEventListener("click", closeBanner);
  closeButton?.addEventListener("click", closeBanner);
}

function bindProfileNotificationModal(root) {
  const modal = root.querySelector("[data-profile-notification-modal]");
  if (!modal) {
    return;
  }

  const titleNode = modal.querySelector("[data-profile-notification-title]");
  const typeNode = modal.querySelector("[data-profile-notification-type]");
  const dateNode = modal.querySelector("[data-profile-notification-date]");
  const messageNode = modal.querySelector("[data-profile-notification-message]");
  const linkNode = modal.querySelector("[data-profile-notification-link]");
  const markReadButton = modal.querySelector("[data-profile-notification-mark-read]");
  const deleteButton = modal.querySelector("[data-profile-notification-delete]");
  const closeButtons = modal.querySelectorAll("[data-profile-notification-close]");
  let activeNotificationId = "";
  let scrollY = 0;

  const openNotificationLink = (href) => {
    if (!href) {
      return;
    }
    window.location.assign(href);
  };

  const markNotificationRead = async (notificationId) => {
    if (!notificationId) {
      return;
    }
    try {
      const response = await fetch(`/api/notifications/${notificationId}/read/`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: "{}",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      root.querySelectorAll(`[data-profile-notification-open][data-notification-id="${notificationId}"]`).forEach((card) => {
        card.dataset.notificationIsRead = "true";
        card.classList.remove("is-unread");
      });
      if (markReadButton && activeNotificationId === String(notificationId)) {
        markReadButton.hidden = true;
      }
    } catch (error) {
      console.warn("Sadaka profile notifications: unable to mark notification as read", error);
    }
  };

  const closeModal = () => {
    modal.hidden = true;
    modal.setAttribute("aria-hidden", "true");
    document.body.classList.remove("is-modal-open");
    document.body.style.removeProperty("--modal-scroll-offset");
    window.scrollTo(0, scrollY);
  };

  const openModal = (trigger) => {
    activeNotificationId = trigger.dataset.notificationId || "";
    titleNode.textContent = trigger.dataset.notificationTitle || "Уведомление";
    typeNode.textContent = trigger.dataset.notificationType || "Уведомление";
    dateNode.textContent = trigger.dataset.notificationDate || "";
    dateNode.setAttribute("datetime", trigger.dataset.notificationDatetime || "");
    messageNode.textContent = trigger.dataset.notificationMessage || "";

    const link = trigger.dataset.notificationLink || "";
    if (link) {
      linkNode.hidden = false;
      linkNode.href = link;
      linkNode.dataset.notificationId = activeNotificationId;
    } else {
      linkNode.hidden = true;
      linkNode.removeAttribute("href");
      delete linkNode.dataset.notificationId;
    }

    if (markReadButton) {
      markReadButton.dataset.notificationId = activeNotificationId;
      markReadButton.hidden = trigger.dataset.notificationIsRead === "true";
    }
    if (deleteButton) {
      deleteButton.dataset.notificationId = activeNotificationId;
    }

    scrollY = window.scrollY || window.pageYOffset || 0;
    document.body.style.setProperty("--modal-scroll-offset", `-${scrollY}px`);
    modal.hidden = false;
    modal.setAttribute("aria-hidden", "false");
    document.body.classList.add("is-modal-open");
  };

  const deleteNotification = async (notificationId) => {
    if (!notificationId) {
      return;
    }
    try {
      const response = await fetch(`/api/notifications/${notificationId}/delete/`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
        body: "{}",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      root.querySelectorAll(`[data-profile-notification-open][data-notification-id="${notificationId}"]`).forEach((card) => {
        card.remove();
      });
      closeModal();
    } catch (error) {
      console.warn("Sadaka profile notifications: unable to delete notification", error);
    }
  };

  root.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-profile-notification-open]");
    if (!trigger) {
      return;
    }
    event.preventDefault();
    openModal(trigger);
  });

  closeButtons.forEach((button) => {
    button.addEventListener("click", () => closeModal());
  });

  modal.addEventListener("click", (event) => {
    const markReadTrigger = event.target.closest("[data-profile-notification-mark-read]");
    if (markReadTrigger?.dataset.notificationId) {
      markNotificationRead(markReadTrigger.dataset.notificationId);
      return;
    }

    const deleteTrigger = event.target.closest("[data-profile-notification-delete]");
    if (deleteTrigger?.dataset.notificationId) {
      deleteNotification(deleteTrigger.dataset.notificationId);
      return;
    }

    const link = event.target.closest("[data-profile-notification-link]");
    if (link?.dataset.notificationId) {
      markNotificationRead(link.dataset.notificationId);
      event.preventDefault();
      openNotificationLink(link.getAttribute("href"));
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) {
      closeModal();
    }
  });
}

function bindProfilePhotoPreview(root) {
  const input = root.querySelector("[data-profile-photo-input]");
  const scope = root.closest(".profile-page-shell") || document;
  const previews = Array.from(scope.querySelectorAll("[data-profile-photo-preview]"));

  if (!input || !previews.length) {
    return;
  }

  input.addEventListener("change", () => {
    const [file] = input.files || [];
    if (!file) {
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      previews.forEach((preview) => {
        preview.style.backgroundImage = `url('${event.target?.result || ""}')`;
        preview.classList.remove("is-placeholder");
        preview.innerHTML = "";
      });
    };
    reader.readAsDataURL(file);
  });
}

function bindGalleryLightbox(root) {
  const lightbox = root.querySelector("[data-gallery-lightbox]");
  const lightboxImage = root.querySelector("[data-gallery-lightbox-image]");
  const lightboxCaption = root.querySelector("[data-gallery-lightbox-caption]");
  const closeButton = root.querySelector("[data-gallery-close]");
  const triggers = root.querySelectorAll("[data-gallery-trigger]");

  if (!lightbox || !lightboxImage || !lightboxCaption || !closeButton || !triggers.length) {
    return;
  }

  if (lightbox.parentElement !== document.body) {
    document.body.appendChild(lightbox);
  }

  const closeLightbox = () => {
    lightbox.hidden = true;
    document.body.classList.remove("is-locked");
    lightboxImage.src = "";
    lightboxImage.alt = "";
    lightboxCaption.textContent = "";
  };

  triggers.forEach((trigger) => {
    trigger.addEventListener("click", () => {
      lightboxImage.src = trigger.dataset.gallerySrc || "";
      lightboxImage.alt = trigger.dataset.galleryAlt || "";
      lightboxCaption.textContent = trigger.dataset.galleryCaption || "";
      lightbox.hidden = false;
      document.body.classList.add("is-locked");
    });
  });

  closeButton.addEventListener("click", closeLightbox);
  lightbox.addEventListener("click", (event) => {
    if (event.target === lightbox) {
      closeLightbox();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !lightbox.hidden) {
      closeLightbox();
    }
  });
}

function bindMobileMenu(root) {
  const mobileToggle = root.querySelector("[data-mobile-toggle]");
  const mobileMenu = root.querySelector("[data-mobile-menu]");
  const mobileOverlay = root.querySelector("[data-mobile-overlay]");
  const closeButton = mobileMenu ? mobileMenu.querySelector("[data-mobile-close]") : null;

  if (!mobileToggle || !mobileMenu) {
    return;
  }

  const mobileMedia = window.matchMedia("(max-width: 768px)");
  const animationDuration = 180;
  let closeTimer = null;

  const openMenu = () => {
    if (closeTimer) {
      window.clearTimeout(closeTimer);
      closeTimer = null;
    }

    mobileToggle.setAttribute("aria-expanded", "true");
    if (mobileOverlay) {
      mobileOverlay.hidden = false;
    }
    window.requestAnimationFrame(() => {
      mobileMenu.classList.add("is-open");
      if (mobileOverlay) {
        mobileOverlay.classList.add("is-open");
      }
    });
    document.body.classList.add("is-locked");
  };

  const closeMenu = () => {
    mobileMenu.classList.remove("is-open");
    mobileToggle.setAttribute("aria-expanded", "false");
    if (mobileOverlay) {
      mobileOverlay.classList.remove("is-open");
    }
    document.body.classList.remove("is-locked");
    closeTimer = window.setTimeout(() => {
      if (mobileOverlay && !mobileOverlay.classList.contains("is-open")) {
        mobileOverlay.hidden = true;
      }
    }, animationDuration);
  };

  mobileToggle.addEventListener("click", (event) => {
    event.stopPropagation();
    const isOpen = mobileMenu.classList.contains("is-open");
    if (isOpen) {
      closeMenu();
      return;
    }
    openMenu();
  });

  mobileMenu.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", (event) => {
      if (!mobileMedia.matches) {
        return;
      }

      const href = link.getAttribute("href");
      const target = link.getAttribute("target");
      const isModifiedClick =
        event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0;

      if (!href || target === "_blank" || isModifiedClick) {
        closeMenu();
        return;
      }

      event.preventDefault();
      closeMenu();
      window.setTimeout(() => {
        window.location.assign(link.href);
      }, 24);
    });
  });

  if (closeButton) {
    closeButton.addEventListener("click", closeMenu);
  }

  if (mobileOverlay) {
    mobileOverlay.addEventListener("click", closeMenu);
  }

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeMenu();
    }
  });

  mobileMedia.addEventListener("change", (event) => {
    if (!event.matches) {
      closeMenu();
    }
  });
}

function bindMosqueWidget(root) {
  const openButton = root.querySelector("[data-mosque-widget-open]");
  const dialog = root.querySelector("[data-mosque-widget-dialog]");
  const overlay = root.querySelector("[data-mosque-widget-overlay]");
  const closeButtons = root.querySelectorAll("[data-mosque-widget-close]");
  const form = root.querySelector("[data-mosque-widget-form]");
  const status = root.querySelector("[data-mosque-widget-status]");
  const submitButton = root.querySelector("[data-mosque-widget-submit]");

  if (!openButton || !dialog || !overlay || !form || !status || !submitButton) {
    return;
  }

  let lastFocusedElement = null;

  const fieldErrors = new Map();
  form.querySelectorAll("[data-field-error]").forEach((node) => {
    fieldErrors.set(node.dataset.fieldError, node);
  });

  const setStatus = (message, type = "") => {
    status.textContent = message || "";
    status.classList.remove("is-success", "is-error");
    if (type) {
      status.classList.add(type === "success" ? "is-success" : "is-error");
    }
  };

  const clearFieldErrors = () => {
    fieldErrors.forEach((node, fieldName) => {
      node.hidden = true;
      node.textContent = "";
      const input = form.elements.namedItem(fieldName);
      if (input && "classList" in input) {
        input.classList.remove("is-invalid");
      }
    });
  };

  const applyFieldErrors = (errors) => {
    Object.entries(errors || {}).forEach(([fieldName, entries]) => {
      const node = fieldErrors.get(fieldName);
      if (!node) {
        return;
      }
      const firstMessage = Array.isArray(entries) && entries[0] ? entries[0].message || "" : "";
      node.textContent = firstMessage;
      node.hidden = !firstMessage;
      const input = form.elements.namedItem(fieldName);
      if (input && "classList" in input) {
        input.classList.toggle("is-invalid", Boolean(firstMessage));
      }
    });
  };

  const closeWidget = () => {
    dialog.hidden = true;
    overlay.hidden = true;
    overlay.classList.remove("is-open");
    document.body.classList.remove("is-locked");
    openButton.setAttribute("aria-expanded", "false");
    if (lastFocusedElement && typeof lastFocusedElement.focus === "function") {
      lastFocusedElement.focus();
    }
  };

  const openWidget = () => {
    lastFocusedElement = document.activeElement;
    clearFieldErrors();
    setStatus("");
    dialog.hidden = false;
    overlay.hidden = false;
    window.requestAnimationFrame(() => {
      overlay.classList.add("is-open");
    });
    document.body.classList.add("is-locked");
    openButton.setAttribute("aria-expanded", "true");
    const firstInput = form.querySelector("input, textarea");
    if (firstInput) {
      window.setTimeout(() => firstInput.focus(), 40);
    }
  };

  openButton.addEventListener("click", () => {
    if (dialog.hidden) {
      openWidget();
      return;
    }
    closeWidget();
  });

  closeButtons.forEach((button) => {
    button.addEventListener("click", closeWidget);
  });

  overlay.addEventListener("click", closeWidget);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !dialog.hidden) {
      closeWidget();
    }
  });

  form.addEventListener("input", (event) => {
    const fieldName = event.target?.name;
    if (!fieldName || !fieldErrors.has(fieldName)) {
      return;
    }
    const errorNode = fieldErrors.get(fieldName);
    if (errorNode) {
      errorNode.hidden = true;
      errorNode.textContent = "";
    }
    event.target.classList.remove("is-invalid");
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearFieldErrors();
    setStatus("");

    submitButton.disabled = true;
    submitButton.dataset.initialLabel = submitButton.dataset.initialLabel || submitButton.textContent;
    submitButton.textContent = "Отправляем...";

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {
          "X-Requested-With": "XMLHttpRequest",
        },
        credentials: "same-origin",
      });

      const payload = await response.json().catch(() => ({}));
      if (!response.ok || !payload.success) {
        applyFieldErrors(payload.errors || {});
        setStatus(payload.message || "Не удалось отправить заявку. Попробуйте позже.", "error");
        return;
      }

      form.reset();
      clearFieldErrors();
      setStatus(payload.message || "Спасибо! Заявка отправлена. Мы свяжемся с вами.", "success");
      window.setTimeout(() => {
        if (!dialog.hidden) {
          closeWidget();
        }
      }, 2200);
    } catch (error) {
      setStatus("Не удалось отправить заявку. Попробуйте позже.", "error");
    } finally {
      submitButton.disabled = false;
      submitButton.textContent = submitButton.dataset.initialLabel || "Отправить заявку";
    }
  });
}

function bindCardLinks(root) {
  root.querySelectorAll("[data-card-link]").forEach((card) => {
    const href = card.dataset.cardLink;
    if (!href) {
      return;
    }

    const isInteractiveTarget = (target) => Boolean(target.closest("a, button, input, select, textarea, label, form"));
    const navigate = () => {
      window.location.href = href;
    };

    card.addEventListener("click", (event) => {
      if (isInteractiveTarget(event.target)) {
        return;
      }
      navigate();
    });

    card.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") {
        return;
      }
      if (isInteractiveTarget(event.target)) {
        return;
      }
      event.preventDefault();
      navigate();
    });
  });
}

function bindProtectedMedia(root) {
  root.querySelectorAll("img, [data-protected-media]").forEach((node) => {
    node.setAttribute("draggable", "false");
    node.style.webkitUserDrag = "none";
    node.addEventListener("dragstart", (event) => event.preventDefault());
    node.addEventListener("contextmenu", (event) => event.preventDefault());
    node.addEventListener("copy", (event) => event.preventDefault());
  });
}

function bindNamazPage(root) {
  const namazRoot = root.querySelector("[data-namaz-root]");
  if (!namazRoot) {
    return;
  }

  const searchUrl = namazRoot.dataset.namazSearchUrl;
  const locateUrl = namazRoot.dataset.namazLocateUrl;
  const dataUrl = namazRoot.dataset.namazDataUrl;
  const cityInput = namazRoot.querySelector("[data-namaz-city-input]");
  const locateButton = namazRoot.querySelector("[data-namaz-locate]");
  const cityChips = namazRoot.querySelectorAll("[data-namaz-city-chip]");
  const searchResults = namazRoot.querySelector("[data-namaz-search-results]");
  const statusNode = namazRoot.querySelector("[data-namaz-status]");
  const cityLabelNode = namazRoot.querySelector("[data-namaz-city-label]");
  const gregorianNode = namazRoot.querySelector("[data-namaz-gregorian-date]");
  const hijriNode = namazRoot.querySelector("[data-namaz-hijri-date]");
  const nextPrayerNode = namazRoot.querySelector("[data-namaz-next-prayer]");
  const prayerGrid = namazRoot.querySelector("[data-namaz-prayer-grid]");
  const calendarList = namazRoot.querySelector("[data-namaz-calendar-list]");
  const monthSummaryNode = namazRoot.querySelector("[data-namaz-month-summary]");
  const monthShell = namazRoot.querySelector("[data-namaz-month-shell]");

  if (!searchUrl || !locateUrl || !dataUrl || !cityInput || !locateButton || !searchResults || !statusNode || !cityLabelNode || !gregorianNode || !hijriNode || !nextPrayerNode || !prayerGrid || !calendarList || !monthSummaryNode || !monthShell) {
    return;
  }

  const prayerOrder = [
    ["Fajr", "Фаджр"],
    ["Sunrise", "Восход"],
    ["Dhuhr", "Зухр"],
    ["Asr", "Аср"],
    ["Maghrib", "Магриб"],
    ["Isha", "Иша"],
  ];

  let searchTimer = null;
  let searchController = null;
  let loadController = null;
  let locationRequestId = 0;
  let resultItems = [];

  const createNode = (tagName, className, text) => {
    const node = document.createElement(tagName);
    if (className) {
      node.className = className;
    }
    if (typeof text === "string") {
      node.textContent = text;
    }
    return node;
  };

  const normalizeTime = (value) => String(value || "—").split(" ")[0];

  const closeSearchResults = () => {
    searchResults.hidden = true;
    searchResults.innerHTML = "";
  };

  const setCookie = (name, value, days = 30) => {
    const expires = new Date(Date.now() + days * 86400000).toUTCString();
    document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
  };

  const saveLocation = (location) => {
    try {
      window.localStorage.setItem("sadaka_namaz_location", JSON.stringify(location));
    } catch (error) {
      // Storage can be unavailable in private mode. Cookie fallback is enough.
    }
    setCookie("sadaka_namaz_city", location.label || location.city || "", 30);
  };

  const loadSavedLocation = () => {
    try {
      const rawValue = window.localStorage.getItem("sadaka_namaz_location");
      return rawValue ? JSON.parse(rawValue) : null;
    } catch (error) {
      return null;
    }
  };

  const setStatus = (message, tone = "neutral") => {
    statusNode.textContent = message;
    statusNode.dataset.tone = tone;
  };

  const claimLocationRequest = () => {
    locationRequestId += 1;
    return locationRequestId;
  };

  const renderIdleState = (message = "Выберите город вручную или разрешите доступ к геолокации.") => {
    cityLabelNode.textContent = "Город не выбран";
    gregorianNode.textContent = "—";
    hijriNode.textContent = "—";
    nextPrayerNode.textContent = "—";
    prayerGrid.innerHTML = prayerOrder
      .map(([, label]) => {
        return `
          <article class="namaz-prayer-card">
            <span>${label}</span>
            <strong>—</strong>
          </article>
        `;
      })
      .join("");
    calendarList.innerHTML = `
      <article class="namaz-calendar-item">
        <strong>Выберите город</strong>
        <span>${message}</span>
      </article>
    `;
    monthSummaryNode.textContent = "Выберите город, и мы покажем расписание на весь месяц.";
    monthShell.innerHTML = '<div class="namaz-month-empty">После выбора города здесь появится расписание на весь месяц.</div>';
  };

  const renderSearchResults = (items) => {
    resultItems = items;
    searchResults.innerHTML = "";
    if (!items.length) {
      searchResults.hidden = false;
      searchResults.append(createNode("div", "namaz-search-empty", "По вашему запросу города не найдены."));
      return;
    }

    searchResults.hidden = false;
    items.forEach((item, index) => {
      const button = createNode("button", "button secondary namaz-search-result");
      button.type = "button";
      button.dataset.namazResultIndex = String(index);
      button.append(createNode("strong", "", item.label || item.city || "Без названия"));
      button.append(createNode("span", "", item.description || ""));
      searchResults.append(button);
    });

    searchResults.querySelectorAll("[data-namaz-result-index]").forEach((button) => {
      button.addEventListener("click", () => {
        const selected = resultItems[Number(button.dataset.namazResultIndex)];
        if (!selected) {
          return;
        }
        cityInput.value = selected.label || selected.city || "";
        closeSearchResults();
        const requestId = claimLocationRequest();
        loadNamazData(selected, `Загружаем время намаза для города ${selected.label || selected.city}…`, requestId);
      });
    });
  };

  const computeNextPrayer = (timings, timezoneName = "") => {
    let currentMinutes = new Date().getHours() * 60 + new Date().getMinutes();
    if (timezoneName) {
      try {
        const parts = new Intl.DateTimeFormat("en-GB", {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
          timeZone: timezoneName,
        }).formatToParts(new Date());
        const hours = Number(parts.find((part) => part.type === "hour")?.value || 0);
        const minutes = Number(parts.find((part) => part.type === "minute")?.value || 0);
        currentMinutes = hours * 60 + minutes;
      } catch (error) {
        // Browser can reject unknown timezones, keep local fallback.
      }
    }

    const nextPrayer = prayerOrder.find(([key]) => {
      const [hours, minutes] = normalizeTime(timings[key]).split(":").map((part) => Number(part));
      return hours * 60 + minutes > currentMinutes;
    });

    return nextPrayer || prayerOrder[0];
  };

  const renderNamazData = (payload) => {
    const location = payload.location || {};
    const timings = payload.timings || {};
    const calendar = payload.calendar || [];
    const monthSchedule = payload.month_schedule || {};
    const nextPrayerFromApi = payload.next_prayer || null;
    const [fallbackNextPrayerKey, fallbackNextPrayerLabel] = computeNextPrayer(timings, payload.timezone || "");
    const nextPrayerKey = nextPrayerFromApi?.key || fallbackNextPrayerKey;
    const nextPrayerLabel = nextPrayerFromApi?.label || fallbackNextPrayerLabel;
    const nextPrayerTime = normalizeTime(nextPrayerFromApi?.time || timings[nextPrayerKey]);

    cityLabelNode.textContent = location.label || location.city || "Не выбран";
    gregorianNode.textContent = payload.gregorian_date || "—";
    hijriNode.textContent = payload.hijri_date || "—";
    nextPrayerNode.textContent = `${nextPrayerLabel} в ${nextPrayerTime}`;

    prayerGrid.innerHTML = prayerOrder
      .map(([key, label]) => {
        const isNext = key === nextPrayerKey;
        return `
          <article class="namaz-prayer-card${isNext ? " is-next" : ""}">
            <span>${label}</span>
            <strong>${normalizeTime(timings[key])}</strong>
          </article>
        `;
      })
      .join("");

    calendarList.innerHTML = "";
    if (calendar.length) {
      calendar.forEach((item) => {
        const article = createNode("article", "namaz-calendar-item");
        article.append(createNode("strong", "", item.title || "Без названия"));
        article.append(createNode("span", "", `${item.gregorian || "—"} • ${item.hijri || "—"}`));
        article.append(createNode("span", "", item.note || ""));
        calendarList.append(article);
      });
    } else {
      const fallbackArticle = createNode("article", "namaz-calendar-item");
      fallbackArticle.append(createNode("strong", "", "Ближайшие даты скоро появятся"));
      fallbackArticle.append(createNode("span", "", "Сейчас не удалось загрузить календарь. Попробуйте обновить страницу чуть позже."));
      calendarList.append(fallbackArticle);
    }

    monthSummaryNode.textContent = `${payload.gregorian_date || "—"} · ${payload.hijri_date || "—"}`;
    const monthRows = Array.isArray(monthSchedule.rows) ? monthSchedule.rows : [];
    if (!monthRows.length) {
      monthShell.innerHTML = '<div class="namaz-month-empty">Пока не удалось показать расписание на месяц. Попробуйте обновить страницу или выбрать город заново.</div>';
      return;
    }

    monthShell.innerHTML = `
      <table class="namaz-month-table">
        <caption>${monthSchedule.month || "Месяц"} ${monthSchedule.year || ""}</caption>
        <thead>
          <tr>
            <th>${monthSchedule.month || "Месяц"}</th>
            <th>Фаджр</th>
            <th>Восход</th>
            <th>Зухр</th>
            <th>Аср</th>
            <th>Магриб</th>
            <th>Иша</th>
          </tr>
        </thead>
        <tbody>
          ${monthRows
            .map((row) => {
              const isToday = row.gregorian === payload.gregorian_date;
              return `
                <tr${isToday ? ' class="is-today"' : ""}>
                  <td>${row.day} (${row.weekday || "—"})</td>
                  <td>${row.fajr || "—"}</td>
                  <td>${row.sunrise || "—"}</td>
                  <td>${row.dhuhr || "—"}</td>
                  <td>${row.asr || "—"}</td>
                  <td>${row.maghrib || "—"}</td>
                  <td>${row.isha || "—"}</td>
                </tr>
              `;
            })
            .join("")}
        </tbody>
      </table>
    `;
  };

  const fetchJson = async (url, params = null, signal = null) => {
    const targetUrl = params ? `${url}?${new URLSearchParams(params).toString()}` : url;
    const response = await fetch(targetUrl, {
      method: "GET",
      headers: {
        Accept: "application/json",
        "X-Requested-With": "XMLHttpRequest",
      },
      credentials: "same-origin",
      signal,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok || payload.success === false) {
      throw new Error(payload.message || "Request failed");
    }
    return payload;
  };

  const loadNamazData = async (location, statusMessage = "Загружаем время намаза…", requestId = claimLocationRequest()) => {
    if (loadController) {
      loadController.abort();
    }
    const controller = new AbortController();
    loadController = controller;
    setStatus(statusMessage);
    try {
      const payload = await fetchJson(dataUrl, {
        lat: String(location.lat),
        lon: String(location.lon),
        city: location.city || "",
        region: location.region || "",
        country: location.country || "",
        country_code: location.country_code || "",
      }, controller.signal);
      if (requestId !== locationRequestId) {
        return;
      }
      renderNamazData(payload);
      saveLocation(location);
      setStatus(`Показываем время намаза для города ${payload.location?.label || location.label || location.city}.`, "success");
    } catch (error) {
      if (error.name === "AbortError" || requestId !== locationRequestId) {
        return;
      }
      renderIdleState("Пока не получилось загрузить данные. Попробуйте выбрать город ещё раз.");
      setStatus(error.message || "Пока не удалось загрузить время намаза. Попробуйте чуть позже.", "error");
    } finally {
      if (loadController === controller) {
        loadController = null;
      }
    }
  };

  const searchCities = async (query) => {
    if (query.trim().length < 2) {
      closeSearchResults();
      return;
    }

    if (searchController) {
      searchController.abort();
    }
    searchController = new AbortController();

    try {
      const payload = await fetchJson(
        searchUrl,
        {
          q: query.trim(),
        },
        searchController.signal
      );
      renderSearchResults(payload.results || []);
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      searchResults.hidden = false;
      searchResults.innerHTML = '<div class="namaz-search-empty">Не удалось выполнить поиск города. Попробуйте еще раз.</div>';
    }
  };

  const locateUser = () => {
    const requestId = claimLocationRequest();
    if (!navigator.geolocation) {
      if (requestId !== locationRequestId) {
        return;
      }
      renderIdleState("В этом браузере геолокация недоступна, поэтому выберите город вручную.");
      setStatus("Выберите свой город вручную или воспользуйтесь быстрыми кнопками ниже.", "error");
      return;
    }

    cityLabelNode.textContent = "Определяем…";
    setStatus("Определяем ваш город…");
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        if (requestId !== locationRequestId) {
          return;
        }
        const coordinates = {
          lat: Number(position.coords.latitude),
          lon: Number(position.coords.longitude),
        };
        try {
          const locationPayload = await fetchJson(locateUrl, coordinates);
          if (requestId !== locationRequestId) {
            return;
          }
          const location = locationPayload.location || coordinates;
          cityInput.value = location.label || location.city || "";
          loadNamazData(location, "Нашли ваш город. Загружаем расписание…", requestId);
        } catch (error) {
          if (requestId !== locationRequestId) {
            return;
          }
          loadNamazData(coordinates, "Определили ваше местоположение. Загружаем расписание по ближайшей точке…", requestId);
        }
      },
      () => {
        if (requestId !== locationRequestId) {
          return;
        }
        renderIdleState("Доступ к геолокации отключён. Выберите город вручную, и мы покажем время намаза и календарь.");
        setStatus("Выберите город вручную или нажмите на один из популярных городов.", "error");
      },
      {
        enableHighAccuracy: false,
        timeout: 4500,
        maximumAge: 1800000,
      }
    );
  };

  cityInput.addEventListener("input", () => {
    const query = cityInput.value;
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
      searchCities(query);
    }, 240);
  });

  cityInput.addEventListener("focus", () => {
    if (cityInput.value.trim().length >= 2 && searchResults.innerHTML.trim() === "") {
      searchCities(cityInput.value);
    }
  });

  cityChips.forEach((button) => {
    button.addEventListener("click", () => {
      const requestId = claimLocationRequest();
      const location = {
        city: button.dataset.city || "",
        region: button.dataset.region || "",
        country: button.dataset.country || "",
        country_code: button.dataset.countryCode || "",
        lat: Number(button.dataset.lat || 0),
        lon: Number(button.dataset.lon || 0),
      };
      location.label = [location.city, location.region].filter(Boolean).join(", ");
      cityInput.value = location.label || location.city;
      closeSearchResults();
      loadNamazData(location, `Загружаем время намаза для города ${location.label || location.city}…`, requestId);
    });
  });

  document.addEventListener("click", (event) => {
    if (!namazRoot.contains(event.target)) {
      closeSearchResults();
      return;
    }
    if (!searchResults.contains(event.target) && event.target !== cityInput) {
      closeSearchResults();
    }
  });

  locateButton.addEventListener("click", locateUser);

  const savedLocation = loadSavedLocation();
  if (savedLocation && savedLocation.lat && savedLocation.lon) {
    cityInput.value = savedLocation.label || savedLocation.city || "";
    const requestId = claimLocationRequest();
    loadNamazData(savedLocation, `Загружаем сохраненное время намаза для города ${savedLocation.label || savedLocation.city}…`, requestId);
    return;
  }

  locateUser();
}

document.addEventListener("DOMContentLoaded", () => {
  bindMobileMenu(document);
  document.querySelectorAll("[data-mosque-widget-root]").forEach((root) => bindMosqueWidget(root));
  bindProtectedMedia(document);
  bindCardLinks(document);

  document.querySelectorAll("[data-donation-shell]").forEach((root) => {
    bindAmountControls(root);
    bindModeControls(root);
    bindPaymentControls(root);
    bindAnonymousSupportControls(root);
    bindSupportTargetControls(root);
  });

  const supportModal = document.querySelector("[data-support-modal]");
  if (supportModal) {
    bindSupportModal(supportModal);
  }

  const helpNowModal = document.querySelector("[data-help-now-modal]");
  if (helpNowModal) {
    bindBasicModal(helpNowModal, {
      triggerSelector: "[data-open-help-now-modal]",
      closeSelector: "[data-close-help-now-modal]",
    });
  }

  document.querySelectorAll("[data-mosque-search-form]").forEach((form) => {
    bindMosqueSearchForm(form);
  });

  document.querySelectorAll("[data-mosque-catalog-search]").forEach((root) => {
    bindMosqueCatalogSearch(root);
  });

  const authShell = document.querySelector("[data-auth-shell]");
  if (authShell) {
    bindAuthFlow(authShell);
  }

  document.querySelectorAll("[data-copy-root]").forEach((root) => {
    bindCopyControl(root);
  });

  const profileTabs = document.querySelector(".profile-tabs");
  if (profileTabs) {
    bindCopyControl(profileTabs);
    bindProfilePhotoPreview(profileTabs);
  }

  const notificationSoundController = createNotificationSoundController();
  document.querySelectorAll("[data-notifications-root]").forEach((root) => {
    bindNotifications(root, notificationSoundController);
  });

  const notificationPage = document.querySelector("[data-notification-page]");
  if (notificationPage) {
    bindNotificationPage(notificationPage, notificationSoundController);
  }

  const cookieBanner = document.querySelector("[data-cookie-banner]");
  if (cookieBanner) {
    bindCookieBanner(cookieBanner);
  }

  const profilePage = document.querySelector(".profile-page-shell");
  if (profilePage) {
    bindProfileNotificationModal(profilePage);
  }

  document.querySelectorAll("[data-lightbox-root]").forEach((root) => {
    bindGalleryLightbox(root);
  });

  document.querySelectorAll("[data-faq-root]").forEach((root) => {
    bindFaq(root);
  });

  document.querySelectorAll("[data-tabs]").forEach((tabsRoot) => {
    const tabButtons = tabsRoot.querySelectorAll("[data-tab-target]");
    const tabPanels = tabsRoot.querySelectorAll("[data-tab-panel]");

    tabButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const target = button.dataset.tabTarget;
        tabButtons.forEach((item) => item.classList.remove("active"));
        tabPanels.forEach((panel) => panel.classList.remove("active"));
        button.classList.add("active");
        const nextPanel = tabsRoot.querySelector(`[data-tab-panel="${target}"]`);
        if (nextPanel) {
          nextPanel.classList.add("active");
        }
      });
    });
  });

  document.querySelectorAll(".detail-card").forEach((card) => {
    bindExpandableText(card);
    bindExpandableList(card);
  });

  bindNamazPage(document);

  const heroStat = document.querySelector("[data-stat-target]");
  if (heroStat) {
    const target = Number(heroStat.dataset.statTarget || 0);
    let current = 0;
    const step = Math.max(1, Math.ceil(target / 40));
    const timer = window.setInterval(() => {
      current += step;
      if (current >= target) {
        current = target;
        window.clearInterval(timer);
      }
      heroStat.textContent = current.toLocaleString("ru-RU");
    }, 35);
  }
});
