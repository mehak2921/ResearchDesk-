document.addEventListener('DOMContentLoaded', () => {
    // Auth Elements
    const authOverlay = document.getElementById('auth-overlay');
    const authForm = document.getElementById('auth-form');
    const authEmail = document.getElementById('auth-email');
    const authPassword = document.getElementById('auth-password');
    const authSubmitBtn = document.getElementById('auth-submit-btn');
    const toggleAuthMode = document.getElementById('toggle-auth-mode');
    const forgotPasswordLink = document.getElementById('forgot-password-link');
    const authTitle = document.getElementById('auth-title');
    const authSubtitle = document.getElementById('auth-subtitle');
    const authError = document.getElementById('auth-error');
    const authSuccess = document.getElementById('auth-success');
    const passwordGroup = document.getElementById('password-group');
    
    // Profile Elements
    const userEmailDisplay = document.getElementById('user-email-display');
    const logoutBtn = document.getElementById('logout-btn');
    const editProfileBtn = document.getElementById('edit-profile-btn');
    const profileModal = document.getElementById('profile-modal');
    const closeProfileBtn = document.getElementById('close-profile-btn');
    const profileForm = document.getElementById('profile-form');
    const newPassword = document.getElementById('new-password');
    const profileMessage = document.getElementById('profile-message');

    // App Elements
    const form = document.getElementById('research-form');
    const input = document.getElementById('topic-input');
    
    // Support submitting textarea on Enter key
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            form.dispatchEvent(new Event('submit'));
        }
    });
    const submitBtn = document.getElementById('submit-btn');
    const loadingState = document.getElementById('loading-state');
    const resultContainer = document.getElementById('result-container');
    const reportContent = document.getElementById('report-content');
    const reportTitle = document.getElementById('report-title');
    const copyBtn = document.getElementById('copy-btn');
    const speakBtn = document.getElementById('speak-btn');
    const downloadPdfBtn = document.getElementById('download-pdf-btn');
    const downloadDocBtn = document.getElementById('download-doc-btn');
    const downloadImgBtn = document.getElementById('download-img-btn');
    const loadingText = document.getElementById('loading-text');
    const historyList = document.getElementById('history-list');
    const newChatBtn = document.getElementById('new-chat-btn');

    // New Interactive Elements
    const clarificationContainer = document.getElementById('clarification-container');
    const clarificationOptions = document.getElementById('clarification-options');
    const customClarificationInput = document.getElementById('custom-clarification-input');
    const customClarificationBtn = document.getElementById('custom-clarification-btn');
    const revisionForm = document.getElementById('revision-form');
    const revisionInput = document.getElementById('revision-input');
    const reviseBtn = document.getElementById('revise-btn');
    const undoBtn = document.getElementById('undo-btn');
    const redoBtn = document.getElementById('redo-btn');
    
    // Mobile Elements
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const closeSidebarBtn = document.getElementById('close-sidebar-btn');
    const sidebar = document.querySelector('.sidebar');

    let isLoginMode = true;
    let isForgotPasswordMode = false;
    let sessionToken = localStorage.getItem('supabase_token');
    let currentUser = JSON.parse(localStorage.getItem('supabase_user') || 'null');

    const loadingMessages = [
        "Evaluating query context...",
        "Deploying AI Agents...",
        "Researcher is gathering data...",
        "Analyzing latest trends...",
        "Writer is drafting the report...",
        "Formatting final output..."
    ];

    let messageInterval;
    let currentTopic = "Research Report";
    
    // Revision History State
    let reportHistory = [];
    let currentReportIndex = -1;

    // --- Authentication Flow ---

    const landingPage = document.getElementById('landing-page');
    const appLayout = document.getElementById('app-layout');
    const getStartedBtn = document.getElementById('get-started-btn');

    if (getStartedBtn) {
        getStartedBtn.addEventListener('click', () => {
            authOverlay.classList.remove('hidden');
        });
    }

    authOverlay.addEventListener('click', (e) => {
        if (e.target === authOverlay && !sessionToken) {
            authOverlay.classList.add('hidden');
        }
    });

    function updateAuthUI() {
        if (sessionToken) {
            if(landingPage) landingPage.style.display = 'none';
            if(appLayout) appLayout.style.display = '';
            authOverlay.classList.add('hidden');
            if (currentUser && currentUser.email) {
                userEmailDisplay.textContent = currentUser.email;
            }
            fetchHistory();
        } else {
            if(landingPage) landingPage.style.display = 'flex';
            if(appLayout) appLayout.style.display = 'none';
            authOverlay.classList.add('hidden');
            resetAuthForm();
        }
    }

    function resetAuthForm() {
        authError.classList.add('hidden');
        authSuccess.classList.add('hidden');
        authEmail.value = '';
        authPassword.value = '';
    }

    function showAuthError(msg) {
        authError.textContent = msg;
        authError.classList.remove('hidden');
        authSuccess.classList.add('hidden');
    }

    function showAuthSuccess(msg) {
        authSuccess.textContent = msg;
        authSuccess.classList.remove('hidden');
        authError.classList.add('hidden');
    }

    toggleAuthMode.addEventListener('click', (e) => {
        e.preventDefault();
        isForgotPasswordMode = false;
        passwordGroup.classList.remove('hidden');
        authPassword.required = true;
        
        isLoginMode = !isLoginMode;
        if (isLoginMode) {
            authTitle.textContent = "Welcome Back";
            authSubtitle.textContent = "Login to access your research agent.";
            authSubmitBtn.querySelector('.btn-text').textContent = "Login";
            toggleAuthMode.textContent = "Need an account? Register";
        } else {
            authTitle.textContent = "Create Account";
            authSubtitle.textContent = "Register to start researching.";
            authSubmitBtn.querySelector('.btn-text').textContent = "Register";
            toggleAuthMode.textContent = "Already have an account? Login";
        }
        resetAuthForm();
    });

    forgotPasswordLink.addEventListener('click', (e) => {
        e.preventDefault();
        isForgotPasswordMode = true;
        isLoginMode = false;
        
        authTitle.textContent = "Reset Password";
        authSubtitle.textContent = "Enter your email to receive a reset link.";
        authSubmitBtn.querySelector('.btn-text').textContent = "Send Link";
        
        passwordGroup.classList.add('hidden');
        authPassword.required = false;
        toggleAuthMode.textContent = "Back to Login";
        
        resetAuthForm();
    });

    authForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = authEmail.value;
        const password = authPassword.value;

        authSubmitBtn.disabled = true;
        
        try {
            if (isForgotPasswordMode) {
                const res = await fetch('/api/auth/reset-password', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email: email, password: "" })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || "Failed to reset password");
                showAuthSuccess(data.message || "Reset email sent!");
            } else {
                const endpoint = isLoginMode ? '/api/auth/login' : '/api/auth/register';
                const res = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ email, password })
                });
                const data = await res.json();
                if (!res.ok) throw new Error(data.detail || "Authentication failed");
                
                if (data.session) {
                    sessionToken = data.session.access_token;
                    currentUser = data.user;
                    localStorage.setItem('supabase_token', sessionToken);
                    localStorage.setItem('supabase_user', JSON.stringify(currentUser));
                    updateAuthUI();
                } else {
                    showAuthSuccess("Please check your email to verify your account.");
                }
            }
        } catch (err) {
            showAuthError(err.message);
        } finally {
            authSubmitBtn.disabled = false;
        }
    });

    logoutBtn.addEventListener('click', () => {
        sessionToken = null;
        currentUser = null;
        localStorage.removeItem('supabase_token');
        localStorage.removeItem('supabase_user');
        
        // Clear UI
        historyList.innerHTML = '';
        reportContent.innerHTML = '';
        resultContainer.classList.add('hidden');
        input.value = '';
        
        updateAuthUI();
    });

    
    // --- Recents Toggle Flow ---
    const recentsToggleBtn = document.getElementById('recents-toggle-btn');
    const recentsCaret = document.getElementById('recents-caret');
    
    if (recentsToggleBtn && historyList && recentsCaret) {
        recentsToggleBtn.addEventListener('click', () => {
            if (historyList.style.display === 'none') {
                historyList.style.display = 'block';
                recentsCaret.classList.remove('ph-caret-right');
                recentsCaret.classList.add('ph-caret-down');
            } else {
                historyList.style.display = 'none';
                recentsCaret.classList.remove('ph-caret-down');
                recentsCaret.classList.add('ph-caret-right');
            }
        });
    }

    
    // --- Sidebar Search Flow ---
    const sidebarSearchBtn = document.getElementById('sidebar-search-btn');
    const sidebarSearchInput = document.getElementById('sidebar-search-input');
    
    if (sidebarSearchBtn && sidebarSearchInput) {
        sidebarSearchBtn.addEventListener('click', () => {
            if (sidebarSearchInput.style.display === 'none') {
                sidebarSearchInput.style.display = 'block';
                sidebarSearchInput.focus();
            } else {
                sidebarSearchInput.style.display = 'none';
                sidebarSearchInput.value = '';
                // Reset filter
                const items = historyList.querySelectorAll('.history-item');
                items.forEach(item => item.style.display = 'flex');
            }
        });
        
        sidebarSearchInput.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();
            const items = historyList.querySelectorAll('.history-item');
            
            items.forEach(item => {
                const title = item.querySelector('h4').textContent.toLowerCase();
                if (title.includes(term)) {
                    item.style.display = 'flex';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }

    
    // --- Desktop Sidebar Toggle ---
    const desktopSidebarToggle = document.getElementById('desktop-sidebar-toggle');
    if (desktopSidebarToggle && sidebar) {
        desktopSidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
        });
    }

    // --- Mobile Sidebar Flow ---
    if (mobileMenuBtn && sidebar && closeSidebarBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            sidebar.classList.add('open');
        });
        
        closeSidebarBtn.addEventListener('click', () => {
            sidebar.classList.remove('open');
        });
        
        document.addEventListener('click', (e) => {
            if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && !mobileMenuBtn.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        });
        
        // Auto-close sidebar on mobile when a history item is clicked
        const originalFetchHistory = fetchHistory;
        fetchHistory = async function() {
            await originalFetchHistory();
        }
    }

    // --- Profile Management ---
    const userProfileBtn = document.getElementById('user-profile-btn');
    const userActionsContainer = document.getElementById('user-actions-container');

    if (userProfileBtn && userActionsContainer) {
        userProfileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            userActionsContainer.classList.toggle('hidden');
        });
        
        // Hide if clicking outside
        document.addEventListener('click', (e) => {
            if (!userProfileBtn.contains(e.target) && !userActionsContainer.contains(e.target)) {
                userActionsContainer.classList.add('hidden');
            }
        });
    }

    editProfileBtn.addEventListener('click', () => {
        if (sidebar) sidebar.classList.remove('open');
        profileModal.classList.remove('hidden');
        newPassword.value = '';
        profileMessage.textContent = '';
    });

    closeProfileBtn.addEventListener('click', () => {
        profileModal.classList.add('hidden');
    });

    profileForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        profileMessage.textContent = "Updating...";
        profileMessage.style.color = 'inherit';
        
        try {
            const res = await fetch('/api/auth/update-password', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${sessionToken}`
                },
                body: JSON.stringify({ new_password: newPassword.value })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || "Failed to update password");
            
            profileMessage.textContent = "Password updated successfully!";
            profileMessage.style.color = '#10b981';
            setTimeout(() => {
                profileModal.classList.add('hidden');
            }, 2000);
        } catch (err) {
            profileMessage.textContent = err.message;
            profileMessage.style.color = '#ef4444';
        }
    });

    // --- App Flow & Revisions ---

    function updateUndoRedoUI() {
        if (currentReportIndex > 0) {
            undoBtn.classList.remove('hidden');
        } else {
            undoBtn.classList.add('hidden');
        }
        
        if (currentReportIndex < reportHistory.length - 1) {
            redoBtn.classList.remove('hidden');
        } else {
            redoBtn.classList.add('hidden');
        }
    }

    undoBtn.addEventListener('click', () => {
        if (currentReportIndex > 0) {
            currentReportIndex--;
            showReport(currentTopic, reportHistory[currentReportIndex], false);
        }
    });

    redoBtn.addEventListener('click', () => {
        if (currentReportIndex < reportHistory.length - 1) {
            currentReportIndex++;
            showReport(currentTopic, reportHistory[currentReportIndex], false);
        }
    });

    async function fetchHistory() {
        if (!sessionToken) return;
        try {
            const res = await fetch('/api/history', {
                headers: {
                    'Authorization': `Bearer ${sessionToken}`
                }
            });
            
            if (res.status === 401) {
                logoutBtn.click();
                return;
            }
            
            const data = await res.json();

            if (data.error) {
                const el = document.createElement('div');
                el.className = 'history-empty';
                el.textContent = data.error;
                historyList.replaceChildren(el);
                return;
            }
            
            if (data.data && data.data.length > 0) {
                historyList.innerHTML = '';
                data.data.forEach(item => {
                    const el = document.createElement('div');
                    el.className = 'history-item';
                    
                    const date = new Date(item.created_at).toLocaleDateString();
                    
                    el.innerHTML = `
                        <div class="history-item-header">
                            <h4>${item.topic}</h4>
                            <button class="delete-history-btn" title="Delete" data-id="${item.id}">
                                <i class="ph ph-trash"></i>
                            </button>
                        </div>
                    `;
                    
                    el.addEventListener('click', (e) => {
                        if (e.target.closest('.delete-history-btn')) {
                            const btn = e.target.closest('.delete-history-btn');
                            deleteHistoryItem(btn.dataset.id, el);
                            return;
                        }
                        
                        // Reset history stack for clicked item
                        reportHistory = [item.report];
                        currentReportIndex = 0;
                        showReport(item.topic, item.report, false);
                        
                        // Close sidebar on mobile
                        sidebar.classList.remove('open');
                    });
                    
                    historyList.appendChild(el);
                });
            } else {
                historyList.innerHTML = `
                    <div class="history-empty">
                        <i class="ph ph-empty-state" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i>
                        <p>No past research found.</p>
                    </div>`;
            }
        } catch (error) {
            console.error("Error fetching history", error);
        }
    }

    async function deleteHistoryItem(itemId, elementNode) {
        if (!confirm("Are you sure you want to delete this report?")) return;
        
        try {
            const res = await fetch(`/api/history/${itemId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${sessionToken}`
                }
            });
            if (res.ok) {
                // Remove from UI
                elementNode.remove();
                if (historyList.children.length === 0) {
                    historyList.innerHTML = `
                        <div class="history-empty">
                            <i class="ph ph-empty-state" style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.5;"></i>
                            <p>No past research found.</p>
                        </div>`;
                }
            } else {
                throw new Error("Failed to delete item.");
            }
        } catch (error) {
            console.error(error);
            alert("Error deleting history item");
        }
    }

    function showReport(topic, markdownReport, pushToHistory = true) {
        currentTopic = topic;
        reportTitle.innerText = topic;
        input.value = topic;
        
        loadingState.classList.add('hidden');
        clarificationContainer.classList.add('hidden');
        resultContainer.classList.remove('hidden');
        reportContent.innerHTML = marked.parse(markdownReport);
        
        if (pushToHistory) {
            // Remove future history if we undo'd and then generated anew
            if (currentReportIndex < reportHistory.length - 1) {
                reportHistory = reportHistory.slice(0, currentReportIndex + 1);
            }
            reportHistory.push(markdownReport);
            currentReportIndex = reportHistory.length - 1;
        }
        updateUndoRedoUI();
    }

    newChatBtn.addEventListener('click', () => {
        if (sidebar) sidebar.classList.remove('open');
        input.value = '';
        currentTopic = "Research Report";
        reportTitle.innerText = "Research Report";
        resultContainer.classList.add('hidden');
        clarificationContainer.classList.add('hidden');
        loadingState.classList.add('hidden');
        reportContent.innerHTML = '';
        reportHistory = [];
        currentReportIndex = -1;
        updateUndoRedoUI();
        input.focus();
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const topic = input.value.trim();
        if (!topic) return;
        
        // Prevent re-running the same search if it is already displayed
        if (topic === currentTopic && !resultContainer.classList.contains('hidden') && reportHistory.length > 0) {
            return;
        }
        
        if (!sessionToken) {
            logoutBtn.click();
            return;
        }

        currentTopic = topic;
        reportTitle.innerText = topic;

        // UI Reset
        submitBtn.disabled = true;
        resultContainer.classList.add('hidden');
        clarificationContainer.classList.add('hidden');
        loadingState.classList.remove('hidden');
        reportContent.innerHTML = '';
        reportHistory = [];
        currentReportIndex = -1;
        updateUndoRedoUI();
        
        let msgIndex = 0;
        loadingText.textContent = loadingMessages[0];
        messageInterval = setInterval(() => {
            msgIndex = (msgIndex + 1) % loadingMessages.length;
            loadingText.textContent = loadingMessages[msgIndex];
        }, 4000);

        try {
            const response = await fetch('/api/research', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${sessionToken}`
                },
                body: JSON.stringify({ topic })
            });

            if (response.status === 401) {
                logoutBtn.click();
                throw new Error("Session expired. Please login again.");
            }
            if (!response.ok) {
                let errorDetail = response.statusText;
                try {
                    const errorJson = await response.json();
                    if (errorJson.detail) {
                        errorDetail = errorJson.detail;
                    }
                } catch (e) {}
                throw new Error(`Server Error: ${errorDetail}`);
            }

            const data = await response.json();
            
            // Check for Clarification Needs
            if (data.status === "clarification_needed") {
                loadingState.classList.add('hidden');
                clarificationContainer.classList.remove('hidden');
                clarificationOptions.innerHTML = '';
                
                data.options.forEach(opt => {
                    const btn = document.createElement('button');
                    btn.className = 'clarification-btn';
                    btn.innerText = opt;
                    btn.type = 'button';
                    btn.addEventListener('click', () => {
                        input.value = opt;
                        form.dispatchEvent(new Event('submit'));
                    });
                    clarificationOptions.appendChild(btn);
                });

                // Clear previous custom input
                customClarificationInput.value = '';

                // Add listeners for custom clarification input
                const submitCustomClarification = () => {
                    const currentInput = document.getElementById('custom-clarification-input');
                    const customTopic = currentInput.value.trim();
                    if (customTopic) {
                        input.value = customTopic;
                        form.dispatchEvent(new Event('submit'));
                    }
                };

                // Remove old listeners to prevent duplicates if shown multiple times
                let currentCustomBtn = document.getElementById('custom-clarification-btn');
                const newCustomBtn = currentCustomBtn.cloneNode(true);
                currentCustomBtn.parentNode.replaceChild(newCustomBtn, currentCustomBtn);
                newCustomBtn.addEventListener('click', submitCustomClarification);
                
                let currentCustomInput = document.getElementById('custom-clarification-input');
                const newCustomInput = currentCustomInput.cloneNode(true);
                currentCustomInput.parentNode.replaceChild(newCustomInput, currentCustomInput);
                newCustomInput.addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        submitCustomClarification();
                    }
                });

                newCustomInput.focus();

                return;
            }
            
            // Normal Success
            showReport(topic, data.result);
            fetchHistory();

        } catch (error) {
            console.error('Research failed:', error);
            reportContent.innerHTML = `<div class="error-msg"><h3>Research Failed</h3><p>${error.message}</p></div>`;
            loadingState.classList.add('hidden');
            resultContainer.classList.remove('hidden');
        } finally {
            submitBtn.disabled = false;
            clearInterval(messageInterval);
            document.querySelector('.progress-fill').style.animation = 'none';
            void document.querySelector('.progress-fill').offsetWidth;
            document.querySelector('.progress-fill').style.animation = 'progress 15s cubic-bezier(0.1, 0.7, 0.1, 1) forwards';
        }
    });

    revisionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const feedback = revisionInput.value.trim();
        if (!feedback) return;
        
        const currentReport = reportHistory[currentReportIndex];
        if (!currentReport) return;
        
        reviseBtn.disabled = true;
        const btnText = reviseBtn.querySelector('.btn-text');
        const originalText = btnText.innerText;
        btnText.innerText = "Revising...";
        
        // Disable search bar temporarily
        submitBtn.disabled = true;
        reportContent.classList.add('revising-state');
        
        try {
            const response = await fetch('/api/revise', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${sessionToken}`
                },
                body: JSON.stringify({ 
                    topic: currentTopic, 
                    current_report: currentReport, 
                    feedback: feedback 
                })
            });

            if (!response.ok) throw new Error(`Error: ${response.status} ${response.statusText}`);

            const data = await response.json();
            
            // Show new revised report, it will get pushed to history stack
            showReport(currentTopic, data.result);
            revisionInput.value = '';
            
            // Refresh history to show the brand new entry
            fetchHistory();

        } catch (error) {
            console.error('Revision failed:', error);
            alert('Failed to revise: ' + error.message);
        } finally {
            reportContent.classList.remove('revising-state');
            reviseBtn.disabled = false;
            submitBtn.disabled = false;
            btnText.innerText = originalText;
        }
    });

    // --- Utilities ---

    copyBtn.addEventListener('click', () => {
        const text = reportContent.innerText;
        navigator.clipboard.writeText(text).then(() => {
            const originalText = copyBtn.innerHTML;
            copyBtn.innerHTML = '<i class="ph-fill ph-check"></i> Copied';
            setTimeout(() => {
                copyBtn.innerHTML = originalText;
            }, 2000);
        });
    });

    let speechChunks = [];
    let currentChunkIndex = 0;

    function playNextChunk() {
        if (currentChunkIndex >= speechChunks.length) {
            speakBtn.innerHTML = '<i class="ph-fill ph-speaker-high"></i> Speak';
            return;
        }
        const utterance = new SpeechSynthesisUtterance(speechChunks[currentChunkIndex]);
        
        utterance.onend = () => {
            currentChunkIndex++;
            playNextChunk();
        };
        
        utterance.onerror = (e) => {
            console.error('Speech synthesis error', e);
            speakBtn.innerHTML = '<i class="ph-fill ph-speaker-high"></i> Speak';
        };

        speechSynthesis.speak(utterance);
    }

    speakBtn.addEventListener('click', () => {
        if ('speechSynthesis' in window) {
            if (speechSynthesis.speaking) {
                speechSynthesis.cancel();
                speakBtn.innerHTML = '<i class="ph-fill ph-speaker-high"></i> Speak';
            } else {
                const text = reportContent.innerText;
                if (!text.trim()) return;
                
                // Chrome bug: Speech API fails silently or stops after 15 seconds on long texts
                // Fix: Split into smaller sentences/chunks and queue them safely for all browsers
                const rawChunks = text.split(/([.!?\n]+)/);
                speechChunks = [];
                let currentChunk = "";
                
                for (let i = 0; i < rawChunks.length; i++) {
                    const chunk = rawChunks[i];
                    if (!chunk) continue;
                    
                    // If it's punctuation, append it to the current chunk
                    if (/^[.!?\n]+$/.test(chunk)) {
                        currentChunk += chunk;
                    } else {
                        // If it's text, decide whether to append or push
                        if ((currentChunk + chunk).length < 200) {
                            currentChunk += chunk;
                        } else {
                            if (currentChunk.trim()) speechChunks.push(currentChunk.trim());
                            currentChunk = chunk;
                        }
                    }
                }
                if (currentChunk.trim()) speechChunks.push(currentChunk.trim());
                
                currentChunkIndex = 0;
                speakBtn.innerHTML = '<i class="ph-fill ph-stop"></i> Stop';
                playNextChunk();
            }
        } else {
            alert("Sorry, your browser doesn't support text to speech!");
        }
    });

    downloadPdfBtn.addEventListener('click', () => {
        const opt = {
            margin:       10,
            filename:     `${currentTopic.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_report.pdf`,
            image:        { type: 'jpeg', quality: 0.98 },
            html2canvas:  { scale: 2, useCORS: true, logging: false },
            jsPDF:        { unit: 'mm', format: 'a4', orientation: 'portrait' },
            pagebreak:    { mode: 'css', avoid: ['tr', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'li'] }
        };
        const clone = reportContent.cloneNode(true);
        clone.classList.add('pdf-export');
        html2pdf().set(opt).from(clone).save();
    });

    downloadDocBtn.addEventListener('click', () => {
        const header = "<html xmlns:o='urn:schemas-microsoft-com:office:office' " +
            "xmlns:w='urn:schemas-microsoft-com:office:word' " +
            "xmlns='http://www.w3.org/TR/REC-html40'>" +
            "<head><meta charset='utf-8'><title>Research Report</title></head><body>";
        const footer = "</body></html>";
        const sourceHTML = header + reportContent.innerHTML + footer;
        
        const blob = new Blob([sourceHTML], { type: 'application/vnd.ms-word;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const fileDownload = document.createElement("a");
        document.body.appendChild(fileDownload);
        fileDownload.href = url;
        fileDownload.download = `${currentTopic.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_report.doc`;
        fileDownload.click();
        document.body.removeChild(fileDownload);
        URL.revokeObjectURL(url);
    });

    downloadImgBtn.addEventListener('click', () => {
        html2canvas(reportContent, {
            backgroundColor: '#0f172a',
            scale: 2,
        }).then(canvas => {
            canvas.toBlob((blob) => {
                if (!blob) return;
                const url = URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.download = `${currentTopic.replace(/[^a-z0-9]/gi, '_').toLowerCase()}_report.png`;
                link.href = url;
                link.click();
                URL.revokeObjectURL(url);
            }, 'image/png');
        });
    });

    // --- Voice Input Logic ---
    function setupVoiceInput(micBtnId, inputFieldId) {
        const micBtn = document.getElementById(micBtnId);
        const inputField = document.getElementById(inputFieldId);
        
        if (!micBtn || !inputField) return;

        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            micBtn.style.display = 'none'; // Hide if not supported
            return;
        }

        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        const recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;

        let isRecording = false;

        micBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (isRecording) {
                recognition.stop();
            } else {
                recognition.start();
            }
        });

        recognition.onstart = () => {
            isRecording = true;
            micBtn.innerHTML = '<i class="ph-fill ph-microphone" style="color: #ef4444;"></i>';
            micBtn.classList.add('recording-pulse');
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            const currentInputField = document.getElementById(inputFieldId);
            const currentVal = currentInputField.value;
            currentInputField.value = currentVal ? currentVal + ' ' + transcript : transcript;
            
            // hide custom placeholder if it's the main textarea
            if (inputFieldId === 'topic-input') {
                const placeholder = currentInputField.parentNode.querySelector('.custom-placeholder');
                if (placeholder) placeholder.style.display = 'none';
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error', event.error);
            isRecording = false;
            micBtn.innerHTML = '<i class="ph ph-microphone"></i>';
            micBtn.classList.remove('recording-pulse');
        };

        recognition.onend = () => {
            isRecording = false;
            micBtn.innerHTML = '<i class="ph ph-microphone"></i>';
            micBtn.classList.remove('recording-pulse');
        };
    }

    setupVoiceInput('mic-main', 'topic-input');
    setupVoiceInput('mic-revision', 'revision-input');
    setupVoiceInput('mic-custom', 'custom-clarification-input');

    // Initialize Auth state
    updateAuthUI();
});








