function doGet(e) {
  return HtmlService.createTemplateFromFile('index')
    .evaluate()
    .setTitle('シフト管理システム')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0');
}

function include(filename) {
  return HtmlService.createHtmlOutputFromFile(filename).getContent();
}

/**
 * ユーティリティ: スプレッドシートの日付オブジェクトを 'YYYY-MM-DD' 文字列に変換
 */
function _formatDateStr(val) {
  if (val instanceof Date) {
    const y = val.getFullYear();
    const m = String(val.getMonth() + 1).padStart(2, '0');
    const d = String(val.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }
  return String(val).trim().replace(/^'/, '');
}

/**
 * ユーティリティ: スプレッドシートの時間オブジェクトを 'HH:mm' 文字列に変換
 */
function _formatTimeStr(val) {
  if (val instanceof Date) {
    const h = String(val.getHours()).padStart(2, '0');
    const m = String(val.getMinutes()).padStart(2, '0');
    return `${h}:${m}`;
  }
  return String(val).trim().replace(/^'/, '');
}

/**
 * 従業員一覧を `Users` シートから取得
 * ※ 関数名の末尾が「_」のものは google.script.run から呼び出せない（サーバー内部専用）
 */
function getStaffList_(includeRetired) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Users');
  if (!sheet) return [];

  const data = sheet.getDataRange().getValues();
  const staffList = [];

  // A:ID, B:PasswordHash, C:Name, D:Role, E:DefaultPosition, F:Status
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() !== '') {
      const retired = String(data[i][5] || '').trim() === STATUS_RETIRED;
      if (retired && !includeRetired) continue;
      staffList.push({
        id: String(data[i][0]).trim(),
        name: String(data[i][2]),
        role: String(data[i][3]),
        defaultPosition: String(data[i][4] || 'ホール'),
        retired: retired
      });
    }
  }
  return staffList;
}

/**
 * ユーティリティ: バイト配列を16進数文字列に変換する
 */
function bytesToHex_(bytes) {
  let hex = '';
  for (let i = 0; i < bytes.length; i++) {
    let v = bytes[i];
    if (v < 0) v += 256;
    hex += (v < 16 ? '0' : '') + v.toString(16);
  }
  return hex;
}

/**
 * ユーティリティ: 文字列を SHA-256 ハッシュ（16進数文字列）に変換する
 */
function _computeSha256(str) {
  return bytesToHex_(Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, str, Utilities.Charset.UTF_8));
}

// =========================================
// 認証・セッション
// =========================================
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000; // ログイン状態の有効期間 (30日)
const LOGIN_MAX_FAILURES = 5;                    // この回数連続で失敗するとロック
const LOGIN_LOCK_SECONDS = 10 * 60;              // ロック時間 (10分)
const ADMIN_ROLE = '管理者';
const STAFF_ROLES = ['一般', ADMIN_ROLE];
const STAFF_POSITIONS = ['ホール', 'キッチン', 'リーダー', '社員'];
const STATUS_RETIRED = '退職'; // Users シート F列。空欄は在籍中
const MSG_LOGIN_FAILED = 'ユーザーIDまたはパスワードが正しくありません。';
const MSG_SESSION_INVALID = 'ログインの有効期限が切れました。もう一度ログインしてください。';

/**
 * ユーザーを1件検索する。見つからなければ null。
 * `Users` シートがない場合は古い「従業員マスター」シートを参照する互換性対応。
 */
function findUser_(staffId) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const target = String(staffId).trim();
  if (!target) return null;

  // Users: A:ID, B:PasswordHash, C:Name, D:Role, E:DefaultPosition, F:Status
  let sheet = ss.getSheetByName('Users');
  let col = { pwd: 1, name: 2, role: 3, pos: 4, status: 5 };
  if (!sheet) {
    // 従業員マスター: A:ID, B:Name, C:Position, D:Password (権限カラムがないため全員一般扱い)
    sheet = ss.getSheetByName('従業員マスター');
    col = { pwd: 3, name: 1, role: -1, pos: 2, status: -1 };
  }
  if (!sheet) return null;

  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() === target) {
      return {
        id: target,
        name: String(data[i][col.name]),
        role: col.role >= 0 ? String(data[i][col.role]) : '一般',
        defaultPosition: String(data[i][col.pos] || 'ホール'),
        stored: String(data[i][col.pwd] || '').trim(),
        retired: col.status >= 0 && String(data[i][col.status] || '').trim() === STATUS_RETIRED,
        sheet: sheet,
        row: i + 1,
        pwdCol: col.pwd + 1
      };
    }
  }
  return null;
}

/**
 * パスワード照合。
 * シートの値は次の3形式を受け付ける:
 *   - 's1$<ソルト>$<ハッシュ>' … ソルト付き (ログイン成功時に自動でこの形式へ変換される)
 *   - SHA-256 ハッシュ (旧形式)
 *   - 「1234」のような平文 (管理者がシートに直接入力した直後)
 */
function checkPassword_(stored, passwordHash) {
  if (!stored || !passwordHash) return { ok: false, legacy: false };
  if (stored.indexOf('s1$') === 0) {
    const parts = stored.split('$');
    return { ok: parts.length === 3 && _computeSha256(parts[1] + passwordHash) === parts[2], legacy: false };
  }
  return { ok: stored === passwordHash || _computeSha256(stored) === passwordHash, legacy: true };
}

function makeSaltedPassword_(passwordHash) {
  const salt = Utilities.getUuid().replace(/-/g, '');
  return 's1$' + salt + '$' + _computeSha256(salt + passwordHash);
}

/**
 * トークン署名用の秘密鍵 (スクリプトプロパティに自動生成して保存)
 */
function getSessionSecret_() {
  const props = PropertiesService.getScriptProperties();
  let secret = props.getProperty('SESSION_SECRET');
  if (!secret) {
    secret = Utilities.getUuid() + Utilities.getUuid();
    props.setProperty('SESSION_SECRET', secret);
  }
  return secret;
}

function signSession_(body, user) {
  // パスワード欄の値も署名に含めることで、パスワード変更時に既存のログイン状態を無効化する
  return bytesToHex_(Utilities.computeHmacSha256Signature(body + '.' + user.stored, getSessionSecret_()));
}

function issueSessionToken_(user) {
  const body = Utilities.base64EncodeWebSafe(user.id, Utilities.Charset.UTF_8) + '.' + (Date.now() + SESSION_TTL_MS);
  return body + '.' + signSession_(body, user);
}

/**
 * トークンを検証してログイン中のユーザーを返す。無効な場合は例外を投げる。
 * データを読み書きする公開関数は、必ず最初にこれを呼ぶこと。
 */
function requireSession_(token, adminOnly) {
  const parts = String(token || '').split('.');
  if (parts.length !== 3 || !(Number(parts[1]) > Date.now())) throw new Error(MSG_SESSION_INVALID);

  let user = null;
  try {
    user = findUser_(Utilities.newBlob(Utilities.base64DecodeWebSafe(parts[0])).getDataAsString());
  } catch (e) {}
  if (!user || user.retired || signSession_(parts[0] + '.' + parts[1], user) !== parts[2]) throw new Error(MSG_SESSION_INVALID);

  if (adminOnly && user.role !== ADMIN_ROLE) throw new Error('この操作を行う権限がありません。');
  return user;
}

/**
 * 書き込み処理を排他制御つきで実行する (同時保存によるデータ消失を防ぐ)
 */
function withLock_(fn) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
  } catch (e) {
    return { success: false, message: '他の人が保存中です。少し待ってからもう一度お試しください。' };
  }
  try {
    const res = fn();
    SpreadsheetApp.flush();
    return res;
  } finally {
    lock.releaseLock();
  }
}

/**
 * スタッフの認証（ログイン）
 * passwordHash はフロントエンド側で SHA-256 ハッシュ化された文字列
 * 成功時は以降の通信に必要なセッショントークンを返す
 */
function authenticateStaff(staffId, passwordHash) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!ss.getSheetByName('Users') && !ss.getSheetByName('従業員マスター')) {
    return { success: false, message: 'ユーザーマスターが存在しません。初期セットアップを実行してください。' };
  }

  // 総当たり対策: 同じIDで連続して失敗したら一定時間ロックする
  const cache = CacheService.getScriptCache();
  const failKey = 'login_fail_' + _computeSha256(String(staffId).trim());
  const failures = Number(cache.get(failKey) || 0);
  if (failures >= LOGIN_MAX_FAILURES) {
    return { success: false, message: 'ログインの失敗が続いたため一時的にロックしています。10分ほど待ってからお試しください。' };
  }

  const user = findUser_(staffId);
  const check = (user && !user.retired) ? checkPassword_(user.stored, String(passwordHash || '')) : { ok: false };
  if (!check.ok) {
    cache.put(failKey, String(failures + 1), LOGIN_LOCK_SECONDS);
    return { success: false, message: MSG_LOGIN_FAILED };
  }
  cache.remove(failKey);

  // 平文・旧形式のパスワードはソルト付きハッシュに置き換える
  if (check.legacy) {
    user.stored = makeSaltedPassword_(String(passwordHash));
    user.sheet.getRange(user.row, user.pwdCol).setValue(user.stored);
  }

  return {
    success: true,
    token: issueSessionToken_(user),
    staff: { id: user.id, name: user.name, role: user.role, defaultPosition: user.defaultPosition }
  };
}

/**
 * 保存済みのログイン状態が有効か確認する (自動ログイン用)
 * 権限などはシートの最新の値を返す
 */
function verifySession(token) {
  try {
    const user = requireSession_(token);
    return { success: true, staff: { id: user.id, name: user.name, role: user.role, defaultPosition: user.defaultPosition } };
  } catch (e) {
    return { success: false, message: e.message };
  }
}

/**
 * 本人によるパスワード変更。
 * currentHash / newHash はフロントエンド側で SHA-256 ハッシュ化された文字列。
 * 変更すると既存のログイン状態が無効になるため、新しいトークンを返す。
 */
function changeMyPassword(token, currentHash, newHash) {
  const session = requireSession_(token);
  currentHash = String(currentHash || '');
  newHash = String(newHash || '');
  // 空文字の SHA-256 (＝新しいパスワードが空) は受け付けない
  const EMPTY_HASH = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
  if (!/^[0-9a-f]{64}$/.test(newHash) || newHash === EMPTY_HASH) {
    return { success: false, message: '新しいパスワードが正しくありません。' };
  }
  if (newHash === currentHash) {
    return { success: false, message: '新しいパスワードが今のパスワードと同じです。' };
  }

  // 総当たり対策: ログイン中の端末を他人に触られても、今のパスワードを当てられないようにする
  const cache = CacheService.getScriptCache();
  const failKey = 'pwchange_fail_' + _computeSha256(session.id);
  const failures = Number(cache.get(failKey) || 0);
  if (failures >= LOGIN_MAX_FAILURES) {
    return { success: false, message: '失敗が続いたため一時的にロックしています。10分ほど待ってからお試しください。' };
  }

  return withLock_(() => {
    const user = findUser_(session.id);
    if (!user || user.retired) return { success: false, message: MSG_SESSION_INVALID };
    if (!checkPassword_(user.stored, currentHash).ok) {
      cache.put(failKey, String(failures + 1), LOGIN_LOCK_SECONDS);
      return { success: false, message: '今のパスワードが正しくありません。' };
    }
    cache.remove(failKey);

    user.stored = makeSaltedPassword_(newHash);
    user.sheet.getRange(user.row, user.pwdCol).setValue(user.stored);
    return { success: true, token: issueSessionToken_(user) };
  });
}

/**
 * ユーティリティ: 「=」などで始まる入力が数式として実行されないよう文字列として保存する
 */
function asText_(val, maxLength) {
  const str = String(val == null ? '' : val).slice(0, maxLength || 200);
  return str === '' ? '' : "'" + str;
}

/**
 * シフト希望データの保存 (`Desired_Shifts` シート)
 */
function submitShiftRequests(token, payload) {
  const user = requireSession_(token);
  // 他人の希望を書き換えられないよう、対象スタッフは必ずログイン情報から決める
  const staffId = user.id;
  const targetMonth = String((payload && payload.targetMonth) || ''); // YYYY-MM
  const shifts = (payload && Array.isArray(payload.shifts)) ? payload.shifts : [];

  if (!/^\d{4}-\d{2}$/.test(targetMonth)) {
    return { success: false, message: '対象月が正しくありません。' };
  }
  const timePattern = /^(\d{1,2}:\d{2}|フリー)?$/;
  const byDate = {};
  for (let i = 0; i < shifts.length; i++) {
    const shift = shifts[i] || {};
    const date = String(shift.date || '');
    const start = String(shift.start || '');
    const end = String(shift.end || '');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || date.indexOf(targetMonth) !== 0 || !start || !timePattern.test(start) || !timePattern.test(end)) {
      return { success: false, message: 'シフト希望の内容が正しくありません。画面を再読み込みしてください。' };
    }
    byDate[date] = { start: start, end: end, memo: shift.memo };
  }

  return withLock_(() => {
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    let sheet = ss.getSheetByName('Desired_Shifts');
    if (!sheet) {
      sheet = ss.insertSheet('Desired_Shifts');
      sheet.appendRow(['UserID', 'Date', 'StartTime', 'EndTime', 'Memo', 'Timestamp']);
    }

    const data = sheet.getDataRange().getValues();

    // 重複を防ぐため、同スタッフ・同月の既存データを一括削除 (下の行から消す)
    for (let i = data.length - 1; i > 0; i--) {
      const sId = String(data[i][0]);
      const dStr = _formatDateStr(data[i][1]);
      if (sId === staffId && dStr.startsWith(targetMonth)) {
        sheet.deleteRow(i + 1);
      }
    }
    SpreadsheetApp.flush();

    const timestamp = new Date();
    const rows = Object.keys(byDate).sort().map(date => [
      staffId,
      "'" + date,
      "'" + byDate[date].start,
      "'" + byDate[date].end,
      asText_(byDate[date].memo),
      timestamp
    ]);

    if (rows.length > 0) {
      sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
    }

    return { success: true };
  });
}

/**
 * 個人の保存済みシフト希望を取得 (提出画面用)
 */
function getSavedShiftRequests(token, targetMonth) {
  const staffId = requireSession_(token).id;
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Desired_Shifts');
  if (!sheet) return {};
  
  const data = sheet.getDataRange().getValues();
  const result = {};
  
  for (let i = 1; i < data.length; i++) {
    const sId = String(data[i][0]);
    const dStr = _formatDateStr(data[i][1]);
    if (sId === String(staffId) && dStr.startsWith(targetMonth)) {
      result[dStr] = {
        start: _formatTimeStr(data[i][2]),
        end: _formatTimeStr(data[i][3]),
        memo: String(data[i][4] || '')
      };
    }
  }
  return result;
}

/**
 * 指定月の個人の確定シフトを取得 (マイシフト用)
 * `Confirmed_Shifts` シートから取得
 */
function getConfirmedShifts(token, targetMonth) {
  const staffId = requireSession_(token).id;
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Confirmed_Shifts');
  if (!sheet) return {};
  
  const data = sheet.getDataRange().getValues();
  const result = {};
  
  for (let i = 1; i < data.length; i++) {
    const dStr = _formatDateStr(data[i][0]);
    const sId = String(data[i][1]);
    if (sId === String(staffId) && dStr.startsWith(targetMonth)) {
      result[dStr] = {
        start: _formatTimeStr(data[i][2]),
        end: _formatTimeStr(data[i][3]),
        restTime: String(data[i][4] || ''),
        position: String(data[i][5] || 'ホール')
      };
    }
  }
  return result;
}

/**
 * 指定日の全員の確定シフトを取得 (全体シフト・出勤メンバー確認用)
 * `Confirmed_Shifts` からその日のシフト一覧を取得し、`Users` と結合してスタッフ名・デフォルト情報を補完
 */
function getDailyConfirmedShifts(token, dateStr) {
  requireSession_(token);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // ユーザーマッピング作成
  const userSheet = ss.getSheetByName('Users');
  const userMap = {};
  if (userSheet) {
    const uData = userSheet.getDataRange().getValues();
    for (let i = 1; i < uData.length; i++) {
      userMap[String(uData[i][0])] = {
        name: String(uData[i][2]),
        role: String(uData[i][3]),
        defaultPosition: String(uData[i][4] || 'ホール')
      };
    }
  }
  
  const sheet = ss.getSheetByName('Confirmed_Shifts');
  if (!sheet) return [];
  
  const data = sheet.getDataRange().getValues();
  const workers = [];
  
  for (let i = 1; i < data.length; i++) {
    const dStr = _formatDateStr(data[i][0]);
    if (dStr === dateStr) {
      const sId = String(data[i][1]);
      const user = userMap[sId] || { name: `不明(${sId})`, role: '一般', defaultPosition: 'ホール' };
      workers.push({
        userId: sId,
        name: user.name,
        position: String(data[i][5] || user.defaultPosition),
        start: _formatTimeStr(data[i][2]),
        end: _formatTimeStr(data[i][3]),
        restTime: String(data[i][4] || '')
      });
    }
  }
  
  return workers;
}

/**
 * 指定月全体の全員の確定シフトを取得 (カレンダー全体表示用)
 */
function getMonthlyConfirmedShifts(token, targetMonth) {
  requireSession_(token);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // ユーザーマップ
  const userSheet = ss.getSheetByName('Users');
  const userMap = {};
  if (userSheet) {
    const uData = userSheet.getDataRange().getValues();
    for (let i = 1; i < uData.length; i++) {
      userMap[String(uData[i][0])] = {
        name: String(uData[i][2]),
        role: String(uData[i][3])
      };
    }
  }
  
  const sheet = ss.getSheetByName('Confirmed_Shifts');
  if (!sheet) return {};
  
  const data = sheet.getDataRange().getValues();
  const result = {}; // { '2026-06-01': [ { name, position, start, end }, ... ] }
  
  for (let i = 1; i < data.length; i++) {
    const dStr = _formatDateStr(data[i][0]);
    if (dStr.startsWith(targetMonth)) {
      const sId = String(data[i][1]);
      const user = userMap[sId] || { name: `不明(${sId})` };
      if (!result[dStr]) result[dStr] = [];
      result[dStr].push({
        userId: sId,
        name: user.name,
        start: _formatTimeStr(data[i][2]),
        end: _formatTimeStr(data[i][3]),
        position: String(data[i][5] || 'ホール')
      });
    }
  }
  return result;
}

/**
 * Googleカレンダーから祝日を取得する
 */
function getHolidays(year, month) {
  const holidays = {};
  try {
    const calendar = CalendarApp.getCalendarById('ja.japanese#holiday@group.v.calendar.google.com');
    if (!calendar) return holidays;
    const startDate = new Date(year, month - 1, 1);
    const endDate = new Date(year, month, 1); // 翌月の1日まで
    const events = calendar.getEvents(startDate, endDate);
    events.forEach(e => {
      const dStr = _formatDateStr(e.getStartTime());
      holidays[dStr] = e.getTitle();
    });
  } catch (e) {
    console.warn('Google Calendar祝日取得エラー: ' + e.message);
  }
  return holidays;
}

/**
 * 管理者: 対象月・期間の全希望状況を取得
 */
function getAdminDesiredShifts(token, targetMonth) {
  requireSession_(token, true);
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const staffList = getStaffList_();
  
  // 希望データを読み込む
  const reqSheet = ss.getSheetByName('Desired_Shifts');
  const reqData = reqSheet ? reqSheet.getDataRange().getValues() : [];
  
  // 希望の整理
  const desiredMap = {}; // { userId: { 'YYYY-MM-DD': { start, end, memo } } }
  for (let i = 1; i < reqData.length; i++) {
    const sId = String(reqData[i][0]);
    const d = _formatDateStr(reqData[i][1]);
    if (!desiredMap[sId]) desiredMap[sId] = {};
    desiredMap[sId][d] = {
      start: _formatTimeStr(reqData[i][2]),
      end: _formatTimeStr(reqData[i][3]),
      memo: String(reqData[i][4] || '')
    };
  }
  
  // すでに確定しているシフトデータも読み込む
  const confSheet = ss.getSheetByName('Confirmed_Shifts');
  const confData = confSheet ? confSheet.getDataRange().getValues() : [];
  const confMap = {}; // { userId: { 'YYYY-MM-DD': { start, end, restTime, position } } }
  for (let i = 1; i < confData.length; i++) {
    const d = _formatDateStr(confData[i][0]);
    const sId = String(confData[i][1]);
    if (!confMap[sId]) confMap[sId] = {};
    confMap[sId][d] = {
      start: _formatTimeStr(confData[i][2]),
      end: _formatTimeStr(confData[i][3]),
      restTime: String(confData[i][4] || ''),
      position: String(confData[i][5] || 'ホール')
    };
  }
  
  // 期間計算 (常に1ヶ月分)
  const [year, month] = targetMonth.split('-').map(Number);
  let startDay = 1;
  let endDay = new Date(year, month, 0).getDate();
  
  const result = [];
  staffList.forEach(staff => {
    const row = {
      id: staff.id,
      name: staff.name,
      role: staff.role,
      defaultPosition: staff.defaultPosition,
      shifts: {}
    };
    for (let d = startDay; d <= endDay; d++) {
      const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      
      const desired = (desiredMap[staff.id] && desiredMap[staff.id][dateStr]) ? desiredMap[staff.id][dateStr] : null;
      const confirmed = (confMap[staff.id] && confMap[staff.id][dateStr]) ? confMap[staff.id][dateStr] : null;
      
      row.shifts[d] = {
        desired: desired,
        confirmed: confirmed
      };
    }
    result.push(row);
  });
  
  return result;
}

/**
 * 管理者: 確定シフトの保存 (`Confirmed_Shifts` シートへの書き込み)
 */
function saveConfirmedShifts(token, payload) {
  requireSession_(token, true);
  if (!payload || !payload.data || payload.data.length === 0) {
    return { success: false, message: 'スタッフデータが空です。画面を再読み込みしてください。' };
  }
  if (!/^\d{4}-\d{2}$/.test(String(payload.targetMonth || ''))) {
    return { success: false, message: '対象月が正しくありません。' };
  }
  return withLock_(() => saveConfirmedShiftsLocked_(payload));
}

function saveConfirmedShiftsLocked_(payload) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Confirmed_Shifts');
  const headerRow = ['Date', 'UserID', 'StartTime', 'EndTime', 'RestTime', 'Position'];
  if (!sheet) {
    sheet = ss.insertSheet('Confirmed_Shifts');
    sheet.appendRow(headerRow);
  }

  const targetMonth = payload.targetMonth; // YYYY-MM
  const [year, month] = targetMonth.split('-').map(Number);

  let startDay = 1;
  let endDay = new Date(year, month, 0).getDate();

  // 保存対象日付のリストを作成
  const targetDates = [];
  for (let d = startDay; d <= endDay; d++) {
    targetDates.push(`${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`);
  }

  // 既存のシートデータを読み込み、今回の対象期間のデータを除外して残す
  const data = sheet.getDataRange().getValues();

  // 削除対象行を除いたデータを再構築
  const finalRows = [];

  // 今回の保存対象スタッフ。ここに含まれない人 (退職者など) の確定シフトは消さずに残す
  const payloadIds = {};
  payload.data.forEach(staff => { payloadIds[String(staff.id)] = true; });

  // 保存されてる行を走査
  for (let i = 1; i < data.length; i++) {
    const dStr = _formatDateStr(data[i][0]);
    // 期間内の日付でない、または今回の保存対象スタッフでなければ残す
    if (!targetDates.includes(dStr) || !payloadIds[String(data[i][1])]) {
      finalRows.push([
        data[i][0] instanceof Date ? data[i][0] : "'" + dStr,
        String(data[i][1]),
        data[i][2] instanceof Date ? data[i][2] : "'" + _formatTimeStr(data[i][2]),
        data[i][3] instanceof Date ? data[i][3] : "'" + _formatTimeStr(data[i][3]),
        "'" + String(data[i][4] || ''),
        String(data[i][5] || 'ホール')
      ]);
    }
  }

  // 今回の確定データを追加
  payload.data.forEach(staff => {
    const staffId = String(staff.id);
    for (let d = startDay; d <= endDay; d++) {
      const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const shift = staff.shifts[d];

      // シフト情報がある場合のみ追加 (未確定は登録しない)
      if (shift && shift.start && shift.start !== '') {
        finalRows.push([
          "'" + dateStr,
          staffId,
          "'" + shift.start,
          "'" + (shift.end || ''),
          "'" + String(shift.restTime || ''),
          String(shift.position || staff.defaultPosition || 'ホール')
        ]);
      }
    }
  });

  // クリアした上で再書き込み
  sheet.clear();
  sheet.appendRow(headerRow);
  if (finalRows.length > 0) {
    sheet.getRange(2, 1, finalRows.length, finalRows[0].length).setValues(finalRows);
  }

  return { success: true };
}

// =========================================
// 管理者: スタッフ管理
// =========================================

/**
 * 編集用に Users シートを取得する。F列 (Status) の見出しがなければ追加する。
 */
function getUsersSheetForEdit_() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Users');
  if (!sheet) return null;
  if (String(sheet.getRange(1, 6).getValue()).trim() === '') {
    sheet.getRange(1, 6).setValue('Status');
  }
  return sheet;
}

/**
 * 初期パスワードを生成する (見間違えやすい 0/o/1/l/i は使わない)
 */
function generatePassword_() {
  const chars = 'abcdefghjkmnpqrstuvwxyz23456789';
  const bytes = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, Utilities.getUuid() + Date.now(), Utilities.Charset.UTF_8);
  let password = '';
  for (let i = 0; i < 8; i++) {
    password += chars.charAt((bytes[i] & 0xff) % chars.length);
  }
  return password;
}

/**
 * 新しいスタッフIDを採番する (既存の数字IDの最大値 + 1 を3桁以上のゼロ埋めで返す)
 */
function nextStaffId_(sheet) {
  const data = sheet.getDataRange().getValues();
  const used = {};
  let max = 0;
  let width = 3;
  for (let i = 1; i < data.length; i++) {
    const id = String(data[i][0]).trim();
    used[id] = true;
    if (/^\d+$/.test(id)) {
      max = Math.max(max, Number(id));
      width = Math.max(width, id.length);
    }
  }
  let next = max + 1;
  let id = String(next).padStart(width, '0');
  while (used[id]) {
    next++;
    id = String(next).padStart(width, '0');
  }
  return id;
}

function validateStaffInput_(input) {
  const name = String((input && input.name) || '').trim();
  const role = String((input && input.role) || '');
  const position = String((input && input.defaultPosition) || '');
  if (!name) return { error: '名前を入力してください。' };
  if (name.length > 30) return { error: '名前は30文字以内で入力してください。' };
  if (STAFF_ROLES.indexOf(role) < 0) return { error: '権限が正しくありません。' };
  if (STAFF_POSITIONS.indexOf(position) < 0) return { error: 'ポジションが正しくありません。' };
  return { name: name, role: role, defaultPosition: position };
}

/**
 * 管理者: スタッフ一覧を取得 (退職者を含む)
 */
function getStaffAdminList(token) {
  requireSession_(token, true);
  return getStaffList_(true);
}

/**
 * 管理者: スタッフを追加する。IDと初期パスワードは自動で発行して返す。
 * パスワードはこの戻り値でしか確認できない (シートにはハッシュだけを保存する)。
 */
function addStaff(token, input) {
  requireSession_(token, true);
  const v = validateStaffInput_(input);
  if (v.error) return { success: false, message: v.error };

  return withLock_(() => {
    const sheet = getUsersSheetForEdit_();
    if (!sheet) return { success: false, message: 'Users シートが見つかりません。' };

    const id = nextStaffId_(sheet);
    const password = generatePassword_();
    sheet.getRange(sheet.getLastRow() + 1, 1, 1, 6).setValues([[
      "'" + id,
      makeSaltedPassword_(_computeSha256(password)),
      asText_(v.name, 30),
      v.role,
      v.defaultPosition,
      ''
    ]]);
    return {
      success: true,
      password: password,
      staff: { id: id, name: v.name, role: v.role, defaultPosition: v.defaultPosition, retired: false }
    };
  });
}

/**
 * 管理者: スタッフの名前・権限・ポジション・在籍状況を更新する。
 * 退職にするとログインできなくなり、シフト作成画面と未提出者一覧から外れる。
 * 過去のシフトは残し、明日以降の確定シフトだけを取り消す。
 */
function updateStaff(token, input) {
  const me = requireSession_(token, true);
  const v = validateStaffInput_(input);
  if (v.error) return { success: false, message: v.error };
  const retired = !!(input && input.retired);

  return withLock_(() => {
    const sheet = getUsersSheetForEdit_();
    const target = sheet ? findUser_(input.id) : null;
    if (!target) return { success: false, message: 'スタッフが見つかりません。画面を再読み込みしてください。' };
    // 管理者が誰もいなくなるのを防ぐため、自分自身の降格・退職はできない
    if (target.id === me.id && (v.role !== ADMIN_ROLE || retired)) {
      return { success: false, message: '自分自身を管理者から外したり、退職にしたりすることはできません。' };
    }

    sheet.getRange(target.row, 3, 1, 4).setValues([[
      asText_(v.name, 30),
      v.role,
      v.defaultPosition,
      retired ? STATUS_RETIRED : ''
    ]]);
    if (retired && !target.retired) removeFutureConfirmedShifts_(target.id);

    return {
      success: true,
      staff: { id: target.id, name: v.name, role: v.role, defaultPosition: v.defaultPosition, retired: retired }
    };
  });
}

/**
 * 管理者: パスワードを再発行する。新しいパスワードはこの戻り値でしか確認できない。
 * 対象スタッフの既存のログイン状態は無効になる。
 */
function resetStaffPassword(token, staffId) {
  const me = requireSession_(token, true);

  return withLock_(() => {
    const sheet = getUsersSheetForEdit_();
    const target = sheet ? findUser_(staffId) : null;
    if (!target) return { success: false, message: 'スタッフが見つかりません。画面を再読み込みしてください。' };

    const password = generatePassword_();
    target.stored = makeSaltedPassword_(_computeSha256(password));
    sheet.getRange(target.row, target.pwdCol).setValue(target.stored);

    const res = { success: true, id: target.id, name: target.name, password: password };
    // 自分のパスワードを変えた場合は、操作を続けられるよう新しいトークンを返す
    if (target.id === me.id) res.token = issueSessionToken_(target);
    return res;
  });
}

/**
 * 指定スタッフの、明日以降の確定シフトを削除する (退職処理用)
 */
function removeFutureConfirmedShifts_(staffId) {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName('Confirmed_Shifts');
  if (!sheet) return;
  const today = _formatDateStr(new Date());
  const data = sheet.getDataRange().getValues();
  for (let i = data.length - 1; i > 0; i--) {
    if (String(data[i][1]) === String(staffId) && _formatDateStr(data[i][0]) > today) {
      sheet.deleteRow(i + 1);
    }
  }
}

/**
 * 【便利ツール】スプレッドシートの初期セットアップ（初回のみ実行）
 */
function setupSpreadsheet() {
  // getUi() はスプレッドシートのメニューから実行したときだけ使える。
  // Webアプリ経由 (google.script.run) ではここで例外になるため、外部から初期化される事故を防げる。
  const ui = SpreadsheetApp.getUi();
  const answer = ui.alert(
    'データベース初期化',
    'ユーザー・希望シフト・確定シフトをすべて消去して初期状態に戻します。よろしいですか？',
    ui.ButtonSet.OK_CANCEL
  );
  if (answer !== ui.Button.OK) return;

  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Users シート
  // A:ID, B:PasswordHash, C:Name, D:Role, E:DefaultPosition, F:Status (空欄=在籍 / 退職)
  let userSheet = ss.getSheetByName('Users');
  if (!userSheet) userSheet = ss.insertSheet('Users');
  userSheet.clear();
  userSheet.appendRow(['ID', 'PasswordHash', 'Name', 'Role', 'DefaultPosition', 'Status']);
  // 初期テストデータ (パスワードは一般が「1234」、管理者が「test」)
  // ※ 本番で使う前に必ず変更すること。B列に新しいパスワードをそのまま入力すれば、
  //    次回ログイン時に自動でソルト付きハッシュへ置き換わる。
  // SHA-256 ハッシュ:
  // "1234" -> "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4"
  // "test" -> "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
  userSheet.appendRow(['001', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', '山田 太郎', '一般', 'キッチン']);
  userSheet.appendRow(['002', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', '佐藤 花子', '一般', 'ホール']);
  userSheet.appendRow(['003', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', '鈴木 一郎', '一般', 'リーダー']);
  userSheet.appendRow(['admin', '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08', '管理者', '管理者', '社員']);
  
  // 2. Desired_Shifts シート
  // A:UserID, B:Date, C:StartTime, D:EndTime, E:Memo, F:Timestamp
  let reqSheet = ss.getSheetByName('Desired_Shifts');
  if (!reqSheet) reqSheet = ss.insertSheet('Desired_Shifts');
  reqSheet.clear();
  reqSheet.appendRow(['UserID', 'Date', 'StartTime', 'EndTime', 'Memo', 'Timestamp']);
  
  // 3. Confirmed_Shifts シート
  // A:Date, B:UserID, C:StartTime, D:EndTime, E:RestTime, F:Position
  let confSheet = ss.getSheetByName('Confirmed_Shifts');
  if (!confSheet) confSheet = ss.insertSheet('Confirmed_Shifts');
  confSheet.clear();
  confSheet.appendRow(['Date', 'UserID', 'StartTime', 'EndTime', 'RestTime', 'Position']);
  
  // 4. System_Settings シート
  // A:Key, B:Value
  let sysSheet = ss.getSheetByName('System_Settings');
  if (!sysSheet) sysSheet = ss.insertSheet('System_Settings');
  sysSheet.clear();
  sysSheet.appendRow(['Key', 'Value']);
  // System_Settings は将来の設定用に空のまま残す
  
  // 古いシートを削除
  const oldSheets = ['従業員マスター', '希望収集', 'シフト表'];
  oldSheets.forEach(name => {
    const s = ss.getSheetByName(name);
    if (s) ss.deleteSheet(s);
  });
  
  console.log('シートの初期セットアップが完了しました！');
}

/**
 * スプレッドシートが開かれたときに実行される関数。
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('シフト管理システム')
    .addItem('データベース初期化・セットアップ', 'setupSpreadsheet')
    .addToUi();
}
