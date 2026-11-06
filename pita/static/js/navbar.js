// Global state
let isAuthenticated = false;
let currentUser = {
    email: '',
    role: '',
    phonenumber: '',
    full_name: '',
    avatar_url: '',
};
let csrfToken = '';
let selectedRole = '';

// Initialize on page load
(async function init() {
    await getCSRFToken();
    await checkAuth();
    
    // Only load profile if authenticated
    if (isAuthenticated) {
        await loadUserProfile();
    } else {
        updateUIForUnauthenticated();
    }
    
    // Child-specific initialization
    if (typeof childInit === 'function') {
        await childInit();
    }
})();

// === CSRF Token ===
async function getCSRFToken() {
    try {
        const response = await fetch(window.GUARDIAN_URLS.csrf);
        const data = await response.json();
        csrfToken = data.csrfToken;
    } catch (error) {
        console.error('Failed to get CSRF token:', error);
    }
}

// === Authentication ===
async function checkAuth() {
    try {
        const response = await fetch(window.GUARDIAN_URLS.checkAuth);
        const data = await response.json();
        isAuthenticated = data.is_authenticated;
    } catch (error) {
        console.error('Auth check failed:', error);
    }
}

// === Load User Profile ===
async function loadUserProfile() {
    try {
        const response = await fetch(window.GUARDIAN_URLS.userProfile);
        const data = await response.json();

        if (data.status === 'success') {
            currentUser.email = data.email;
            currentUser.phonenumber = data.phonenumber || '';
            currentUser.role = data.role || '';
            currentUser.full_name = data.full_name || '';
            currentUser.avatar_url = data.avatar_url || '';

            updateUIWithUserData();
        }
    } catch (error) {
        console.error('Failed to load profile:', error);
    }
}

// === Update UI for Unauthenticated Users ===
function updateUIForUnauthenticated() {
    // Show login link
    const loginLink = document.getElementById('loginLink');
    const mobileLoginLink = document.getElementById('mobileLoginLink');
    if (loginLink) loginLink.style.display = 'inline-block';
    if (mobileLoginLink) mobileLoginLink.style.display = 'block';
    
    // Hide profile button
    const profileBtn = document.getElementById('profileBtn');
    if (profileBtn) profileBtn.style.display = 'none';
    
    // Hide mobile profile section
    const mobileProfileSection = document.getElementById('mobileProfileSection');
    if (mobileProfileSection) mobileProfileSection.style.display = 'none';
    
    // Hide all role-specific links
    hideAllRoleLinks();
}

// === Update UI with User Data ===
function updateUIWithUserData() {
    // Hide login link
    const loginLink = document.getElementById('loginLink');
    const mobileLoginLink = document.getElementById('mobileLoginLink');
    if (loginLink) loginLink.style.display = 'none';
    if (mobileLoginLink) mobileLoginLink.style.display = 'none';
    
    // Show profile button
    const profileBtn = document.getElementById('profileBtn');
    if (profileBtn) profileBtn.style.display = 'flex';
    
    // Show mobile profile section
    const mobileProfileSection = document.getElementById('mobileProfileSection');
    if (mobileProfileSection) mobileProfileSection.style.display = 'block';
    
    // Update navbar email
    const navEmail = document.getElementById('navUserEmail');
    if (navEmail) navEmail.textContent = currentUser.full_name || currentUser.email.split('@')[0];

    // Update mobile menu email
    const mobileEmail = document.getElementById('mobileUserEmail');
    if (mobileEmail) mobileEmail.textContent = currentUser.email;

    // Avatar, initials fallback
    const initials = currentUser.full_name
        ? currentUser.full_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase()
        : currentUser.email.slice(0, 2).toUpperCase();

    function _setAvatar(imgId, initialsId, url, text) {
        const img = document.getElementById(imgId);
        const ini = document.getElementById(initialsId);
        if (!img || !ini) return;
        if (url) {
            img.src = url;
            img.classList.remove('hidden');
            ini.classList.add('hidden');
        } else {
            ini.textContent = text;
            ini.classList.remove('hidden');
            img.classList.add('hidden');
        }
    }
    _setAvatar('navAvatarImg', 'navAvatarInitials', currentUser.avatar_url, initials);
    _setAvatar('modalAvatarImg', 'modalAvatarInitials', currentUser.avatar_url, initials);

    const modalAvatarName = document.getElementById('modalAvatarName');
    if (modalAvatarName) modalAvatarName.textContent = currentUser.full_name || currentUser.email;

    // Update modal
    const modalEmail = document.getElementById('modalUserEmail');
    if (modalEmail) modalEmail.textContent = currentUser.email;

    const modalRole = document.getElementById('modalUserRole');
    if (modalRole) modalRole.textContent = currentUser.role.charAt(0).toUpperCase() + currentUser.role.slice(1);

    const phoneInput = document.getElementById('phoneInput');
    if (phoneInput) phoneInput.value = currentUser.phonenumber || '';

    // Profile fields
    const f = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    f('fullNameInput', currentUser.full_name);
    
    // Set active role
    selectedRole = currentUser.role;
    updateRoleUI();
    
    // Update role-specific links
    updateRoleLinks();
}

// === Hide All Role Links ===
function hideAllRoleLinks() {
    // Desktop
    ['staffLinks', 'parentLinks', 'adminLinks', 'mobileStaffLinks', 'mobileParentLinks', 'mobileAdminLinks']
        .forEach((id) => { const el = document.getElementById(id); if (el) el.style.display = 'none'; });
}

// === Update Role Links ===
function updateRoleLinks() {
    // Hide all first
    hideAllRoleLinks();
    
    // Show appropriate links based on role
    // child = learning links, parent = family portal, analyst = workspace
    const groups = { child: 'StaffLinks', parent: 'ParentLinks', analyst: 'AdminLinks' };
    const group = groups[currentUser.role];
    if (!group) return;
    const desktop = document.getElementById(group.charAt(0).toLowerCase() + group.slice(1));
    const mobile = document.getElementById('mobile' + group);
    if (desktop) desktop.style.display = 'inline';
    if (mobile) mobile.style.display = 'block';
}

// === Role Management === (REMOVED FOR SECURITY)
// Role selection removed - roles are assigned by administrators only
function selectRole(role) {
    // Disabled - roles cannot be changed by users
    console.warn('Role selection is disabled for security purposes');
}

function updateRoleUI() {
    // Disabled - no role selection UI
}

// === Save Profile ===
async function saveProfile() {
    const saveBtn = document.getElementById('saveProfileBtn');
    const saveBtnText = document.getElementById('saveProfileText');
    const saveBtnSpinner = document.getElementById('saveProfileSpinner');

    const resetBtn = () => {
        saveBtn.disabled = false;
        saveBtnText.textContent = 'Save Changes';
        saveBtnSpinner.classList.add('hidden');
    };

    try {
        saveBtn.disabled = true;
        saveBtnText.textContent = 'Saving...';
        saveBtnSpinner.classList.remove('hidden');

        const payload = {
            phonenumber: document.getElementById('phoneInput')?.value || '',
            full_name: document.getElementById('fullNameInput')?.value || '',
        };

        const response = await fetch(window.GUARDIAN_URLS.userProfile, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
            body: JSON.stringify(payload),
        });

        const data = await response.json();
        resetBtn();

        if (data.status !== 'success') {
            showToast(data.message || 'Failed to update profile', 'error');
            return;
        }

        showToast('Profile updated successfully!', 'success');
        closeProfileModal();
        await loadUserProfile();

    } catch (error) {
        console.error('Error saving profile:', error);
        showToast('Failed to save profile', 'error');
        resetBtn();
    }
}

// === Profile Picture, preview → confirm flow ===
let _pendingPictureFile = null;

function previewProfilePicture(input) {
    const file = input.files[0];
    if (!file) return;
    _pendingPictureFile = file;

    const reader = new FileReader();
    reader.onload = function(e) {
        const preview = document.getElementById('picturePreviewArea');
        const previewImg = document.getElementById('picturePreviewImg');
        const fileName = document.getElementById('picturePreviewFileName');
        const hint = document.getElementById('pictureUploadHint');
        if (previewImg) previewImg.src = e.target.result;
        if (fileName) fileName.textContent = file.name;
        if (preview) preview.classList.remove('hidden');
        if (hint) hint.classList.add('hidden');
    };
    reader.readAsDataURL(file);
}

function cancelProfilePicture() {
    _pendingPictureFile = null;
    const preview = document.getElementById('picturePreviewArea');
    const hint = document.getElementById('pictureUploadHint');
    const input = document.getElementById('pictureUpload');
    if (preview) preview.classList.add('hidden');
    if (hint) hint.classList.remove('hidden');
    if (input) input.value = '';
}

async function confirmProfilePicture() {
    if (!_pendingPictureFile) return;
    const status = document.getElementById('pictureUploadStatus');
    const preview = document.getElementById('picturePreviewArea');

    if (status) { status.textContent = 'Uploading…'; status.className = 'text-xs mt-1 text-on-surface-variant'; status.classList.remove('hidden'); }
    if (preview) preview.classList.add('hidden');

    const fd = new FormData();
    fd.append('profile_picture', _pendingPictureFile);
    _pendingPictureFile = null;

    try {
        const res = await fetch(window.GUARDIAN_URLS.profilePicture, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body: fd,
        });
        const data = await res.json();
        const hint = document.getElementById('pictureUploadHint');
        if (hint) hint.classList.remove('hidden');
        if (data.status === 'success') {
            currentUser.avatar_url = data.avatar_url;
            const applyImg = (imgId, initialsId, url) => {
                const img = document.getElementById(imgId);
                const ini = document.getElementById(initialsId);
                if (img && ini) { img.src = url; img.classList.remove('hidden'); ini.classList.add('hidden'); }
            };
            applyImg('navAvatarImg', 'navAvatarInitials', data.avatar_url);
            applyImg('modalAvatarImg', 'modalAvatarInitials', data.avatar_url);
            if (status) { status.textContent = 'Photo updated!'; status.className = 'text-xs mt-1 text-teal'; }
            setTimeout(() => { if (status) status.classList.add('hidden'); }, 3000);
        } else {
            if (status) { status.textContent = data.message || 'Upload failed.'; status.className = 'text-xs mt-1 text-error'; }
        }
    } catch (e) {
        if (status) { status.textContent = 'Upload failed.'; status.className = 'text-xs mt-1 text-error'; }
        const hint = document.getElementById('pictureUploadHint');
        if (hint) hint.classList.remove('hidden');
    }
    document.getElementById('pictureUpload').value = '';
}

// === Delete Account ===
async function handleDeleteAccount() {
    // First confirmation
    const confirmText = 'DELETE';
    const userInput = prompt(
        `⚠️ WARNING: This will permanently delete your account and ALL data!\n\n` +
        `This includes:\n` +
        `- Your profile and personal information\n` +
        `- All orders (for buyers)\n` +
        `- All products and sales (for sellers)\n` +
        `- Your wishlist and cart\n\n` +
        `This action CANNOT be undone!\n\n` +
        `Type "${confirmText}" to confirm deletion:`
    );
    
    if (userInput !== confirmText) {
        if (userInput !== null) {
            showToast('Account deletion cancelled', 'error');
        }
        return;
    }
    
    // Second confirmation
    if (!confirm('Are you absolutely sure? This is your last chance to cancel.')) {
        showToast('Account deletion cancelled', 'error');
        return;
    }
    
    try {
        const response = await fetch(window.GUARDIAN_URLS.deleteAccount, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'success') {
            showToast('Account deleted successfully. Goodbye!', 'success');
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        } else {
            showToast(data.message || 'Failed to delete account', 'error');
        }
    } catch (error) {
        console.error('Error deleting account:', error);
        showToast('Failed to delete account', 'error');
    }
}



// === Mobile Menu ===
function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    const hamburger = document.getElementById('hamburger');
    
    if (menu && hamburger) {
        menu.classList.toggle('hidden');
        hamburger.classList.toggle('active');
    }
}

function closeMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    const hamburger = document.getElementById('hamburger');
    
    if (menu && hamburger) {
        menu.classList.add('hidden');
        hamburger.classList.remove('active');
    }
}

// === Profile Modal ===
function openProfileModal() {
    if (!isAuthenticated) {
        window.location.href = window.GUARDIAN_URLS.login;
        return;
    }
    
    const modal = document.getElementById('profileModal');
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        document.body.style.overflow = 'hidden';
    }
}

function closeProfileModal() {
    cancelProfilePicture();
    const modal = document.getElementById('profileModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
        document.body.style.overflow = 'auto';
    }
}

// Close modal on overlay click
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('profileModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target.id === 'profileModal') {
                closeProfileModal();
            }
        });
    }
});

// === Logout ===
async function handleLogout() {
    if (!confirm('Are you sure you want to logout?')) return;
    
    try {
        const response = await fetch(window.GUARDIAN_URLS.logout, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken
            }
        });

        if (response.ok) {
            window.location.href = window.GUARDIAN_URLS.login;
        }
    } catch (error) {
        console.error('Logout failed:', error);
        showToast('Logout failed', 'error');
    }
}

// === Toast Notifications ===
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if (toast) {
        toast.textContent = message;
        toast.className = `toast ${type} show`;
        
        setTimeout(() => {
            toast.classList.remove('show');
        }, 3000);
    }
}

// === Utility: Close mobile menu on window resize ===
window.addEventListener('resize', () => {
    if (window.innerWidth > 768) {
        closeMobileMenu();
    }
});