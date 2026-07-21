"""Injected tab-bar JavaScript for the Cloudflare WebView window."""

from __future__ import annotations

_TAB_BAR_SCRIPT = """
        (function () {
            var oldBar = document.getElementById('netfix-cloudflare-tabs');
            if (oldBar) {
                oldBar.remove();
            }
            var oldToggle = document.getElementById('netfix-cloudflare-tabs-toggle');
            if (oldToggle) {
                oldToggle.remove();
            }
            var oldRecovery = document.getElementById('netfix-cloudflare-recovery');
            if (oldRecovery) {
                oldRecovery.remove();
            }
            var oldWaitGuard = document.getElementById('netfix-cloudflare-wait-guard');
            if (oldWaitGuard) {
                oldWaitGuard.remove();
            }

            var tabs = __TABS__;
            var activeTab = __ACTIVE_TAB__;
            var netfixTargetUrl = __TARGET_URL__;
            var netfixCurrentIsError = __CURRENT_IS_ERROR__;
            var netfixNeedsLaunchGuard = __NEEDS_LAUNCH_GUARD__;
            var tabCount = Math.max(tabs.length, 1);
            var compactTabs = tabCount > 5;
            var denseTabs = tabCount > 8;
            var tabBasis = denseTabs ? '74px' : (compactTabs ? '92px' : '124px');
            var tabMaxWidth = denseTabs ? '104px' : (compactTabs ? '126px' : '158px');

            var bar = document.createElement('div');
            bar.id = 'netfix-cloudflare-tabs';
            bar.style.position = 'fixed';
            bar.style.top = '10px';
            bar.style.left = '50%';
            bar.style.transform = 'translateX(-50%)';
            bar.style.zIndex = '2147483647';
            bar.style.display = 'flex';
            bar.style.flexWrap = 'wrap';
            bar.style.alignItems = 'center';
            bar.style.gap = '4px';
            bar.style.padding = '4px';
            bar.style.maxWidth = 'calc(100vw - 36px)';
            bar.style.maxHeight = '112px';
            bar.style.overflowX = 'hidden';
            bar.style.overflowY = 'auto';
            bar.style.border = '1px solid rgba(0, 229, 255, 0.55)';
            bar.style.borderRadius = '8px';
            bar.style.background = '#111827';
            bar.style.boxShadow = '0 8px 22px rgba(0,0,0,0.28)';

            function isWebviewErrorUrl(value) {
                try {
                    var protocol = new URL(value || '', window.location.href).protocol.toLowerCase();
                    return protocol === 'chrome-error:' || protocol === 'edge-error:';
                } catch (error) {
                    return false;
                }
            }

            function activeBrowserUrl() {
                var href = window.location.href || '';
                if ((netfixCurrentIsError || isWebviewErrorUrl(href)) && netfixTargetUrl) {
                    return netfixTargetUrl;
                }
                return href;
            }

            function normalizeNavigationUrl(value) {
                value = (value || '').trim();
                if (!value || value.indexOf('javascript:') === 0 || value.indexOf('#') === 0) {
                    return '';
                }
                if (isWebviewErrorUrl(value)) {
                    return '';
                }
                if (value.indexOf('//') === 0) {
                    return 'https:' + value;
                }
                if (!/^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(value) && value.indexOf('.') !== -1 && value.indexOf(' ') === -1) {
                    return 'https://' + value;
                }
                try {
                    return new URL(value, activeBrowserUrl() || window.location.href).href;
                } catch (error) {
                    return '';
                }
            }

            function schemeOf(url) {
                try {
                    return new URL(url, window.location.href).protocol.replace(':', '').toLowerCase();
                } catch (error) {
                    return '';
                }
            }

            function shouldOpenExternal(url) {
                return ['mailto', 'tel', 'sms', 'tg', 'whatsapp'].indexOf(schemeOf(url)) !== -1;
            }

            function openExternal(url) {
                var next = normalizeNavigationUrl(url);
                if (!next) {
                    return;
                }
                if (window.pywebview && window.pywebview.api && window.pywebview.api.open_external) {
                    window.pywebview.api.open_external(next).catch(function () {});
                } else {
                    window.location.href = next;
                }
            }

            function go(url) {
                var next = normalizeNavigationUrl(url);
                if (next) {
                    if (shouldOpenExternal(next)) {
                        openExternal(next);
                        return;
                    }
                    window.location.href = next;
                }
            }

            function openInNewNetfixTab(url, title) {
                var next = normalizeNavigationUrl(url);
                if (!next) {
                    return;
                }
                if (shouldOpenExternal(next)) {
                    openExternal(next);
                    return;
                }
                if (window.pywebview && window.pywebview.api && window.pywebview.api.open_new_tab) {
                    window.pywebview.api.open_new_tab(next, title || 'New Tab').then(function (targetUrl) {
                        if (targetUrl) {
                            window.location.href = targetUrl;
                        }
                    }).catch(function () {
                        window.location.href = next;
                    });
                } else {
                    window.location.href = next;
                }
            }

            function openExistingNetfixTab(tab) {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.open_tab) {
                    window.pywebview.api.open_tab(tab.id).then(function (targetUrl) {
                        if (targetUrl) {
                            window.location.href = targetUrl;
                        }
                    }).catch(function () {
                        go(tab.url);
                    });
                } else {
                    go(tab.url);
                }
            }

            function closeNetfixTab(tab, wrapper) {
                if (window.pywebview && window.pywebview.api && window.pywebview.api.close_tab) {
                    window.pywebview.api.close_tab(tab.id).then(function (targetUrl) {
                        if (targetUrl && targetUrl !== 'closed') {
                            window.location.href = targetUrl;
                        } else if (targetUrl === 'closed' && wrapper) {
                            wrapper.remove();
                        }
                    }).catch(function () {});
                }
            }

            function makeAddressBar() {
                var form = document.createElement('form');
                form.style.display = 'flex';
                form.style.gap = '4px';
                form.style.alignItems = 'center';
                form.style.marginLeft = '6px';
                form.style.flex = '1 1 280px';
                form.style.minWidth = '220px';
                form.onsubmit = function (event) {
                    event.preventDefault();
                    go(input.value);
                };

                function tinyButton(text, title, action) {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.textContent = text;
                    btn.title = title;
                    btn.style.height = '32px';
                    btn.style.minWidth = '32px';
                    btn.style.padding = '0 9px';
                    btn.style.border = '0';
                    btn.style.borderRadius = '5px';
                    btn.style.background = '#1f2937';
                    btn.style.color = '#e5e7eb';
                    btn.style.font = '700 12px Segoe UI, Arial, sans-serif';
                    btn.style.cursor = 'pointer';
                    btn.onclick = action;
                    return btn;
                }

                var input = document.createElement('input');
                input.value = activeBrowserUrl();
                input.title = 'Current URL';
                input.style.width = 'min(360px, 34vw)';
                input.style.minWidth = '130px';
                input.style.flex = '1 1 160px';
                input.style.height = '32px';
                input.style.border = '1px solid rgba(148,163,184,.45)';
                input.style.borderRadius = '5px';
                input.style.background = '#0f172a';
                input.style.color = '#e5e7eb';
                input.style.padding = '0 10px';
                input.style.font = '500 12px Segoe UI, Arial, sans-serif';
                input.onclick = function () {
                    input.select();
                };

                var button = document.createElement('button');
                button.textContent = 'Go';
                button.title = 'Open URL';
                button.style.height = '32px';
                button.style.padding = '0 10px';
                button.style.border = '0';
                button.style.borderRadius = '5px';
                button.style.background = '#0ea5e9';
                button.style.color = '#e5e7eb';
                button.style.font = '700 12px Segoe UI, Arial, sans-serif';
                button.style.cursor = 'pointer';

                var back = tinyButton('<', 'Back', function () { history.back(); });
                var forward = tinyButton('>', 'Forward', function () { history.forward(); });
                var reload = tinyButton('R', 'Reload', function () {
                    if (isWebviewErrorUrl(window.location.href)) {
                        go(activeBrowserUrl());
                        return;
                    }
                    window.location.reload();
                });
                var external = tinyButton('Open', 'Open current URL in your browser', function () { openExternal(input.value || activeBrowserUrl()); });

                form.appendChild(back);
                form.appendChild(forward);
                form.appendChild(reload);
                form.appendChild(input);
                form.appendChild(button);
                form.appendChild(external);

                window.setInterval(function () {
                    var nextValue = activeBrowserUrl();
                    if (document.activeElement !== input && input.value !== nextValue) {
                        input.value = nextValue;
                    }
                }, 800);

                return form;
            }

            function makeTab(tab) {
                var wrapper = document.createElement('div');
                wrapper.style.display = 'flex';
                wrapper.style.alignItems = 'center';
                wrapper.style.height = '32px';
                wrapper.style.flex = '1 1 ' + tabBasis;
                wrapper.style.minWidth = denseTabs ? '66px' : '82px';
                wrapper.style.maxWidth = tabMaxWidth;

                var btn = document.createElement('button');
                btn.textContent = tab.title;
                btn.title = tab.url;
                btn.style.height = '32px';
                btn.style.flex = '1 1 auto';
                btn.style.minWidth = '0';
                btn.style.maxWidth = '100%';
                btn.style.overflow = 'hidden';
                btn.style.textOverflow = 'ellipsis';
                btn.style.whiteSpace = 'nowrap';
                btn.style.padding = tab.closable ? (denseTabs ? '0 6px' : '0 8px') : (denseTabs ? '0 8px' : '0 12px');
                btn.style.border = '0';
                btn.style.borderRadius = tab.closable ? '5px 0 0 5px' : '5px';
                btn.style.background = tab.id === activeTab ? '#075985' : '#1f2937';
                btn.style.color = '#e5e7eb';
                btn.style.font = (denseTabs ? '600 11px' : '600 12px') + ' Segoe UI, Arial, sans-serif';
                btn.style.cursor = 'pointer';
                btn.onmouseenter = function () { btn.style.background = '#374151'; };
                btn.onmouseleave = function () { btn.style.background = tab.id === activeTab ? '#075985' : '#1f2937'; };
                btn.onclick = function () { openExistingNetfixTab(tab); };
                wrapper.appendChild(btn);

                if (tab.closable) {
                    var closeTab = document.createElement('button');
                    closeTab.textContent = 'x';
                    closeTab.title = 'Close tab';
                    closeTab.style.height = '32px';
                    closeTab.style.width = denseTabs ? '22px' : '26px';
                    closeTab.style.flex = '0 0 ' + (denseTabs ? '22px' : '26px');
                    closeTab.style.padding = '0';
                    closeTab.style.border = '0';
                    closeTab.style.borderLeft = '1px solid rgba(255,255,255,0.08)';
                    closeTab.style.borderRadius = '0 5px 5px 0';
                    closeTab.style.background = tab.id === activeTab ? '#075985' : '#1f2937';
                    closeTab.style.color = '#ff8fa3';
                    closeTab.style.font = '700 12px Segoe UI, Arial, sans-serif';
                    closeTab.style.cursor = 'pointer';
                    closeTab.onmouseenter = function () { closeTab.style.background = '#7f1d1d'; };
                    closeTab.onmouseleave = function () { closeTab.style.background = tab.id === activeTab ? '#075985' : '#1f2937'; };
                    closeTab.onclick = function (event) {
                        event.preventDefault();
                        event.stopPropagation();
                        closeNetfixTab(tab, wrapper);
                    };
                    wrapper.appendChild(closeTab);
                }

                return wrapper;
            }

            tabs.forEach(function (tab) {
                bar.appendChild(makeTab(tab));
            });
            bar.appendChild(makeAddressBar());

            var close = document.createElement('button');
            close.textContent = 'x';
            close.title = 'Hide tabs';
            close.style.height = '32px';
            close.style.width = '32px';
            close.style.padding = '0';
            close.style.border = '0';
            close.style.borderRadius = '5px';
            close.style.background = '#1f2937';
            close.style.color = '#ff6b81';
            close.style.font = '600 12px Segoe UI, Arial, sans-serif';
            close.style.cursor = 'pointer';
            close.onclick = function () {
                bar.style.display = 'none';
                toggle.style.display = 'block';
            };
            bar.appendChild(close);

            var toggle = document.createElement('button');
            toggle.id = 'netfix-cloudflare-tabs-toggle';
            toggle.textContent = 'Tabs';
            toggle.title = 'Show NetFix tabs';
            toggle.style.position = 'fixed';
            toggle.style.top = '10px';
            toggle.style.right = '12px';
            toggle.style.zIndex = '2147483647';
            toggle.style.display = 'none';
            toggle.style.height = '32px';
            toggle.style.padding = '0 12px';
            toggle.style.border = '1px solid rgba(0, 229, 255, 0.55)';
            toggle.style.borderRadius = '6px';
            toggle.style.background = '#111827';
            toggle.style.color = '#e5e7eb';
            toggle.style.font = '600 12px Segoe UI, Arial, sans-serif';
            toggle.style.cursor = 'pointer';
            toggle.onclick = function () {
                bar.style.display = 'flex';
                toggle.style.display = 'none';
            };

            function installLinkHandlers() {
                window.open = function (url, target) {
                    if (url) {
                        openInNewNetfixTab(url, target || 'New Tab');
                    }
                    return null;
                };

                document.addEventListener('click', function (event) {
                    var link = event.target && event.target.closest ? event.target.closest('a[href]') : null;
                    if (!link || link.closest('#netfix-cloudflare-tabs')) {
                        return;
                    }
                    if ((link.target && link.target !== '_self') || event.ctrlKey || event.metaKey || event.shiftKey) {
                        event.preventDefault();
                        event.stopPropagation();
                        openInNewNetfixTab(link.getAttribute('href'), link.textContent || link.title || 'New Tab');
                    }
                }, true);

                document.addEventListener('auxclick', function (event) {
                    if (event.button !== 1) {
                        return;
                    }
                    var link = event.target && event.target.closest ? event.target.closest('a[href]') : null;
                    if (!link || link.closest('#netfix-cloudflare-tabs')) {
                        return;
                    }
                    event.preventDefault();
                    event.stopPropagation();
                    openInNewNetfixTab(link.getAttribute('href'), link.textContent || link.title || 'New Tab');
                }, true);

                document.addEventListener('submit', function (event) {
                    var form = event.target;
                    if (!form || !form.closest || form.closest('#netfix-cloudflare-tabs')) {
                        return;
                    }
                    if (form.target && form.target !== '_self') {
                        event.preventDefault();
                        event.stopPropagation();
                        openInNewNetfixTab(form.action || window.location.href, form.getAttribute('aria-label') || 'New Tab');
                    }
                }, true);
            }

            function installErrorRecovery() {
                var bodyText = ((document.body && document.body.innerText) || '').toLowerCase();
                var activeUrl = activeBrowserUrl();
                var errorLike = isWebviewErrorUrl(window.location.href) ||
                    bodyText.indexOf('err_cert') !== -1 ||
                    bodyText.indexOf('certificate') !== -1 ||
                    bodyText.indexOf('your connection is not private') !== -1 ||
                    bodyText.indexOf('this site can') !== -1 ||
                    bodyText.indexOf('hmmm') !== -1;
                if (!errorLike || !activeUrl || document.getElementById('netfix-cloudflare-recovery')) {
                    return;
                }

                var panel = document.createElement('div');
                panel.id = 'netfix-cloudflare-recovery';
                panel.style.position = 'fixed';
                panel.style.left = '50%';
                panel.style.top = '74px';
                panel.style.transform = 'translateX(-50%)';
                panel.style.zIndex = '2147483646';
                panel.style.display = 'flex';
                panel.style.flexDirection = 'column';
                panel.style.gap = '10px';
                panel.style.alignItems = 'stretch';
                panel.style.width = 'min(560px, calc(100vw - 36px))';
                panel.style.padding = '14px 16px';
                panel.style.borderRadius = '8px';
                panel.style.border = '1px solid rgba(125, 211, 252, 0.65)';
                panel.style.background = '#111827';
                panel.style.color = '#e5e7eb';
                panel.style.boxShadow = '0 14px 30px rgba(0,0,0,0.34)';
                panel.style.font = '600 12px Segoe UI, Arial, sans-serif';
                panel.style.lineHeight = '1.55';

                function recoveryButton(text, action) {
                    var btn = document.createElement('button');
                    btn.textContent = text;
                    btn.style.height = '30px';
                    btn.style.border = '0';
                    btn.style.borderRadius = '5px';
                    btn.style.padding = '0 10px';
                    btn.style.background = '#0ea5e9';
                    btn.style.color = '#07111f';
                    btn.style.font = '700 12px Segoe UI, Arial, sans-serif';
                    btn.style.cursor = 'pointer';
                    btn.onclick = action;
                    return btn;
                }

                var label = document.createElement('span');
                label.textContent = 'Chrome/WebView panel is still preparing.';
                label.title = activeUrl;
                label.style.color = '#f8fafc';
                label.style.font = '800 14px Segoe UI, Arial, sans-serif';
                panel.appendChild(label);

                var tipFa = document.createElement('div');
                tipFa.dir = 'rtl';
                tipFa.lang = 'fa';
                tipFa.textContent = 'این پنل در حال آماده شدن است. لطفا ۲ تا ۳ دقیقه دیگر صفحه را Refresh کنید. اگر باز نشد، یک بار کامل برنامه را ببندید و دوباره باز کنید.';
                tipFa.style.color = '#dbeafe';
                tipFa.style.textAlign = 'right';
                panel.appendChild(tipFa);

                var tipEn = document.createElement('div');
                tipEn.lang = 'en';
                tipEn.textContent = 'Tip: This panel is still preparing. Refresh the page in 2-3 minutes. If it still does not open, fully close the app and open it again.';
                tipEn.style.color = '#cbd5e1';
                panel.appendChild(tipEn);

                var actions = document.createElement('div');
                actions.style.display = 'flex';
                actions.style.flexWrap = 'wrap';
                actions.style.gap = '8px';
                actions.style.alignItems = 'center';
                actions.appendChild(recoveryButton('Retry / Refresh', function () { go(activeBrowserUrl()); }));
                actions.appendChild(recoveryButton('Open Browser', function () { openExternal(activeBrowserUrl()); }));
                try {
                    var retryUrl = new URL(activeUrl);
                    if (retryUrl.protocol === 'https:') {
                        actions.appendChild(recoveryButton('Try HTTP', function () {
                            retryUrl.protocol = 'http:';
                            go(retryUrl.href);
                        }));
                    }
                } catch (error) {
                }
                panel.appendChild(actions);
                document.documentElement.appendChild(panel);
            }

            function pageLooksBlocked() {
                var bodyText = ((document.body && document.body.innerText) || '').toLowerCase();
                var titleText = ((document.title || '') + '').toLowerCase();
                if (isWebviewErrorUrl(window.location.href)) {
                    return true;
                }
                if (bodyText.indexOf('err_cert') !== -1 ||
                    bodyText.indexOf('certificate') !== -1 ||
                    bodyText.indexOf('your connection is not private') !== -1 ||
                    bodyText.indexOf('this site can') !== -1 ||
                    bodyText.indexOf('chromewebdata') !== -1 ||
                    bodyText.indexOf('hmmm') !== -1 ||
                    titleText.indexOf('error') !== -1 ||
                    titleText.indexOf('not found') !== -1) {
                    return true;
                }
                return document.readyState === 'loading' || (!bodyText.trim() && !titleText.trim());
            }

            function requestBrowserFallback(reason) {
                var target = activeBrowserUrl();
                if (!target || !window.pywebview || !window.pywebview.api || !window.pywebview.api.open_browser_fallback) {
                    return;
                }
                window.pywebview.api.open_browser_fallback(target, reason || 'webview-timeout').catch(function () {});
            }

            function installForcedWaitGuard() {
                if (!netfixNeedsLaunchGuard || document.getElementById('netfix-cloudflare-wait-guard')) {
                    return;
                }

                var guard = document.createElement('div');
                guard.id = 'netfix-cloudflare-wait-guard';
                guard.style.position = 'fixed';
                guard.style.inset = '0';
                guard.style.zIndex = '2147483647';
                guard.style.display = 'grid';
                guard.style.placeItems = 'center';
                guard.style.background = 'rgba(15, 23, 42, 0.88)';
                guard.style.backdropFilter = 'blur(12px)';
                guard.style.color = '#e5e7eb';
                guard.style.font = '600 13px Segoe UI, Arial, sans-serif';
                guard.style.cursor = 'wait';

                var box = document.createElement('div');
                box.style.width = 'min(420px, calc(100vw - 40px))';
                box.style.padding = '22px 24px';
                box.style.borderRadius = '8px';
                box.style.border = '1px solid rgba(125, 211, 252, 0.55)';
                box.style.background = '#111827';
                box.style.boxShadow = '0 24px 70px rgba(0,0,0,0.42)';

                var title = document.createElement('div');
                title.textContent = 'Please wait';
                title.style.font = '800 18px Segoe UI, Arial, sans-serif';
                title.style.marginBottom = '8px';
                title.style.color = '#f8fafc';

                var message = document.createElement('div');
                message.textContent = 'NetFix is checking this panel. If WebView cannot load it, Chrome or Firefox will open it automatically.';
                message.style.lineHeight = '1.55';
                message.style.color = '#cbd5e1';
                message.style.marginBottom = '16px';

                var status = document.createElement('div');
                status.style.display = 'flex';
                status.style.justifyContent = 'space-between';
                status.style.alignItems = 'center';
                status.style.gap = '12px';
                status.style.color = '#bae6fd';

                var label = document.createElement('span');
                label.textContent = 'Forced wait';
                var counter = document.createElement('span');
                counter.textContent = '5s';
                counter.style.minWidth = '34px';
                counter.style.textAlign = 'right';

                var progress = document.createElement('div');
                progress.style.height = '6px';
                progress.style.marginTop = '12px';
                progress.style.borderRadius = '999px';
                progress.style.overflow = 'hidden';
                progress.style.background = '#1f2937';

                var progressFill = document.createElement('div');
                progressFill.style.height = '100%';
                progressFill.style.width = '0%';
                progressFill.style.background = '#38bdf8';
                progressFill.style.transition = 'width 1s linear';

                status.appendChild(label);
                status.appendChild(counter);
                progress.appendChild(progressFill);
                box.appendChild(title);
                box.appendChild(message);
                box.appendChild(status);
                box.appendChild(progress);
                guard.appendChild(box);
                document.documentElement.appendChild(guard);

                var remaining = 5;
                var tick = window.setInterval(function () {
                    remaining -= 1;
                    counter.textContent = Math.max(remaining, 0) + 's';
                    progressFill.style.width = ((5 - remaining) / 5 * 100) + '%';
                }, 1000);

                window.setTimeout(function () {
                    window.clearInterval(tick);
                    progressFill.style.width = '100%';
                    if (pageLooksBlocked()) {
                        label.textContent = 'Opening in Chrome or Firefox';
                        counter.textContent = '';
                        requestBrowserFallback('webview-not-ready');
                        window.setTimeout(function () {
                            guard.remove();
                        }, 1200);
                        return;
                    }
                    label.textContent = 'Panel is ready';
                    counter.textContent = '';
                    window.setTimeout(function () {
                        guard.remove();
                    }, 450);
                }, 5000);
            }

            document.documentElement.appendChild(bar);
            document.documentElement.appendChild(toggle);
            installLinkHandlers();
            installForcedWaitGuard();
            window.setTimeout(installErrorRecovery, 600);
        })();
"""


def build_tab_bar_script(
    tabs: str,
    active_tab: str,
    target_url: str,
    current_is_error: str,
    needs_launch_guard: str,
) -> str:
    return (
        _TAB_BAR_SCRIPT
        .replace("__TABS__", tabs)
        .replace("__ACTIVE_TAB__", active_tab)
        .replace("__TARGET_URL__", target_url)
        .replace("__CURRENT_IS_ERROR__", current_is_error)
        .replace("__NEEDS_LAUNCH_GUARD__", needs_launch_guard)
    )
