// The browser holds an HttpOnly cookie; account credentials never enter localStorage.
window.studioUser = null;
window.showStudioLogin = () => {
  window.studioUser = null;
  document.body.classList.add('account-locked');
  document.getElementById('accountPanel').hidden = false;
  document.getElementById('logoutButton').hidden = true;
  document.getElementById('accountName').textContent = '';
  window.dispatchEvent(new Event('studio-session-ended'));
};

(() => {
  const el = id => document.getElementById(id);
  let registering = false;
  el('accountToggle').onclick = () => {
    registering = !registering;
    el('accountTitle').textContent = registering ? '创建你的账号' : '登录角色工作室';
    el('accountSubmit').textContent = registering ? '创建账号并进入' : '登录';
    el('accountToggle').textContent = registering ? '已有账号？返回登录' : '没有账号？创建账号';
    el('accountPassword').autocomplete = registering ? 'new-password' : 'current-password';
    el('accountPassLabel').hidden = !registering;
    el('accountPassHint').hidden = !registering;
    el('accountPass').hidden = !registering;
    el('accountPass').disabled = !registering;
    el('accountPass').required = registering;
    if (!registering) el('accountPass').value = '';
    el('accountError').textContent = '';
    window.studioMotion.swap(el('accountForm'));
  };
  el('accountForm').onsubmit = async event => {
    event.preventDefault();
    el('accountSubmit').disabled = true;
    el('accountToggle').disabled = true;
    el('accountError').textContent = '';
    window.studioMotion.button(el('accountSubmit'), 'pending', registering ? '正在创建账号…' : '正在登录…');
    try {
      const credentials = {username: el('accountUsername').value, password: el('accountPassword').value};
      if (registering) credentials.registration_pass = el('accountPass').value.trim();
      const response = await fetch(`/api/auth/${registering ? 'register' : 'login'}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(credentials)
      });
      const result = await response.json();
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '请检查用户名和密码格式。');
      el('accountPassword').value = '';
      el('accountPass').value = '';
      window.studioMotion.button(el('accountSubmit'), 'success', '已完成，即将进入');
      await window.studioMotion.leave(el('accountPanel'));
      window.location.reload();
    } catch (error) {
      el('accountError').textContent = error.message;
      window.studioMotion.error(el('accountForm'));
    } finally {
      window.studioMotion.button(el('accountSubmit'), 'idle', registering ? '创建账号并进入' : '登录');
      el('accountSubmit').disabled = false;
      el('accountToggle').disabled = false;
    }
  };
  el('logoutButton').onclick = async () => {
    el('logoutButton').disabled = true;
    try {
      const response = await fetch('/api/auth/logout', {method: 'POST'});
      if (!response.ok && response.status !== 401) throw new Error('退出失败，请重试。');
      window.location.reload();
    } catch (error) {
      el('logoutButton').disabled = false;
      alert(error.message);
    }
  };
  window.studioAuthReady = new Promise(resolve => {
    fetch('/api/auth/me').then(async response => {
      if (!response.ok) {
        if (response.status !== 401) el('accountError').textContent = '服务暂时不可用，请稍后刷新。';
        return;
      }
      const user = await response.json();
      window.studioUser = user;
      el('accountName').textContent = user.username;
      el('accountPanel').hidden = true;
      el('logoutButton').hidden = false;
      document.body.classList.remove('account-locked');
      resolve(user);
    }).catch(() => {el('accountError').textContent = '无法连接服务，请稍后刷新。';});
  });
})();
