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
 */
function getStaffList() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Users');
  if (!sheet) return [];
  
  const data = sheet.getDataRange().getValues();
  const staffList = [];
  
  // A:ID, B:PasswordHash, C:Name, D:Role, E:DefaultPosition
  for (let i = 1; i < data.length; i++) {
    if (data[i][0]) {
      staffList.push({
        id: String(data[i][0]),
        name: String(data[i][2]),
        role: String(data[i][3]),
        defaultPosition: String(data[i][4] || 'ホール')
      });
    }
  }
  return staffList;
}

/**
 * ユーティリティ: 文字列を SHA-256 ハッシュ（16進数文字列）に変換する
 */
function _computeSha256(str) {
  const rawHash = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, str);
  let hexHash = '';
  for (let i = 0; i < rawHash.length; i++) {
    let hashVal = rawHash[i];
    if (hashVal < 0) hashVal += 256;
    let hexString = hashVal.toString(16);
    if (hexString.length === 1) hexString = '0' + hexString;
    hexHash += hexString;
  }
  return hexHash;
}

/**
 * スタッフの認証（ログイン）
 * passwordHash はフロントエンド側で SHA-256 ハッシュ化された文字列
 */
function authenticateStaff(staffId, passwordHash) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Users');
  
  // 新しい Users シートがない場合は、古い「従業員マスター」シートを参照する互換性対応
  if (!sheet) {
    sheet = ss.getSheetByName('従業員マスター');
    if (!sheet) return { success: false, message: 'ユーザーマスターが存在しません。初期セットアップを実行してください。' };
    
    const data = sheet.getDataRange().getValues();
    for (let i = 1; i < data.length; i++) {
      const id = String(data[i][0]).trim();
      if (id === String(staffId).trim()) {
        const storedVal = String(data[i][3] || '').trim(); // D列: パスワード
        const computedHash = _computeSha256(storedVal);
        
        // シート側が平文またはハッシュどちらでも一致するようにする
        if (storedVal === passwordHash || computedHash === passwordHash) {
          return {
            success: true,
            staff: {
              id: id,
              name: String(data[i][1]),
              role: '一般', // 古いシートには権限カラムがないため一般扱い
              defaultPosition: String(data[i][2] || 'ホール')
            }
          };
        } else {
          return { success: false, message: 'パスワードが間違っています。' };
        }
      }
    }
    return { success: false, message: 'ユーザーが見つかりません。' };
  }
  
  // 新しい Users シートでの処理
  const data = sheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    const id = String(data[i][0]).trim();
    if (id === String(staffId).trim()) {
      const storedVal = String(data[i][1] || '').trim(); // B列: パスワード
      const computedHash = _computeSha256(storedVal);
      
      // シート側に「1234」のような平文が書かれていても、
      // GAS側でハッシュ化して画面側から送られてきたハッシュと一致するか判定する
      if (storedVal === passwordHash || computedHash === passwordHash) {
        return {
          success: true,
          staff: {
            id: id,
            name: String(data[i][2]),
            role: String(data[i][3]),
            defaultPosition: String(data[i][4] || 'ホール')
          }
        };
      } else {
        return { success: false, message: 'パスワードが間違っています。' };
      }
    }
  }
  return { success: false, message: 'ユーザーが見つかりません。' };
}

/**
 * シフト希望データの保存 (`Desired_Shifts` シート)
 */
function submitShiftRequests(payload) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName('Desired_Shifts');
  if (!sheet) {
    sheet = ss.insertSheet('Desired_Shifts');
    sheet.appendRow(['UserID', 'Date', 'StartTime', 'EndTime', 'Memo', 'Timestamp']);
  }
  
  const data = sheet.getDataRange().getValues();
  const staffId = String(payload.staffId);
  const targetMonth = payload.targetMonth; // YYYY-MM

  // 重複を防ぐため、同スタッフ・同月の既存データを削除
  for (let i = data.length - 1; i > 0; i--) {
    const sId = String(data[i][0]);
    const dStr = _formatDateStr(data[i][1]);
    if (sId === staffId && dStr.startsWith(targetMonth)) {
      sheet.deleteRow(i + 1);
    }
  }
  SpreadsheetApp.flush();

  const timestamp = new Date();
  const rows = payload.shifts.map(shift => [
    staffId,
    "'" + shift.date,
    "'" + shift.start,
    "'" + shift.end,
    shift.memo || '',
    timestamp
  ]);
  
  if (rows.length > 0) {
    sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
  }
  
  return { success: true };
}

/**
 * 個人の保存済みシフト希望を取得 (提出画面用)
 */
function getSavedShiftRequests(staffId, targetMonth) {
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
function getConfirmedShifts(staffId, targetMonth) {
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
function getDailyConfirmedShifts(dateStr) {
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
function getMonthlyConfirmedShifts(targetMonth) {
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
function getAdminDesiredShifts(targetMonth) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const staffList = getStaffList();
  
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
function saveConfirmedShifts(payload) {
  if (!payload || !payload.data || payload.data.length === 0) {
    return { success: false, message: 'スタッフデータが空です。画面を再読み込みしてください。' };
  }
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

  // 保存されてる行を走査
  for (let i = 1; i < data.length; i++) {
    const dStr = _formatDateStr(data[i][0]);
    // 期間内の日付でなければ残す
    if (!targetDates.includes(dStr)) {
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

/**
 * 【便利ツール】スプレッドシートの初期セットアップ（初回のみ実行）
 */
function setupSpreadsheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Users シート
  // A:ID, B:PasswordHash, C:Name, D:Role, E:DefaultPosition
  let userSheet = ss.getSheetByName('Users');
  if (!userSheet) userSheet = ss.insertSheet('Users');
  userSheet.clear();
  userSheet.appendRow(['ID', 'PasswordHash', 'Name', 'Role', 'DefaultPosition']);
  // 初期テストデータ (パスワードはすべて一般が「1234」、管理者が「9999」)
  // SHA-256 ハッシュ:
  // "1234" -> "03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4"
  // "9999" -> "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
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
  sysSheet.appendRow(['deadline_day', '20']);
  
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
