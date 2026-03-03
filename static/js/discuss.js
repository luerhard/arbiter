export function renderOnlineStatus(online_users) {
  const exampleField = document.getElementById("n-online-status");
  const count = Array.isArray(online_users) ? online_users.length : 0;
  exampleField.innerText = count;
}
