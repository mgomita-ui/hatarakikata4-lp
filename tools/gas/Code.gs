/**
 * 働き方4.0 LP — 問い合わせフォームの受け口（Google Apps Script / ウェブアプリ）
 *
 * このスクリプトは「スプレッドシートに紐づいたプロジェクト」に貼る前提です
 * （LP から届いた内容を、そのシートに 1 行ずつ追記し、通知メールを送ります）。
 *
 * デプロイ: デプロイ > 新しいデプロイ > 種類「ウェブアプリ」
 *   次のユーザーとして実行: 自分
 *   アクセスできるユーザー: 全員
 * → 表示された「ウェブアプリの URL（…/exec）」を LP 側の GAS_URL に設定する。
 *
 * LP 側は Content-Type を付けずに JSON 文字列を POST する（ブラウザの CORS 事前確認を
 * 発生させないため）。ここでは postData.contents を JSON として読む。
 */

var NOTIFY_TO = 'm.gomita@canvas-sr.jp';   // 通知先
var SHEET_NAME = '問い合わせ';               // 追記先シート名（無ければ作る）

function doPost(e) {
  var out = { ok: false };
  try {
    var body = {};
    try { body = JSON.parse((e && e.postData && e.postData.contents) || '{}'); } catch (err) { body = (e && e.parameter) || {}; }

    // 迷惑投稿対策: 隠し欄が埋まっていたら黙って成功扱いにして捨てる
    if (body._honey) { out.ok = true; return json_(out); }

    var row = {
      受信日時: new Date(),
      会社名: s_(body.company),
      お名前: s_(body.name),
      メール: s_(body.email),
      従業員数: s_(body.size),
      困っていること: s_(body.msg),
      送信元: s_(body.page || ''),
      UA: s_(body.ua || '')
    };
    if (!row.会社名 || !row.お名前 || !row.メール) { out.error = 'required'; return json_(out); }

    appendRow_(row);
    notify_(row);
    out.ok = true;
  } catch (err) {
    out.error = String(err && err.message || err);
  }
  return json_(out);
}

// 動作確認用: ブラウザで /exec を開くと ok が返る
function doGet() { return json_({ ok: true, service: 'hatarakikata4-lp inquiry' }); }

function appendRow_(row) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  var keys = Object.keys(row);
  if (sh.getLastRow() === 0) {
    sh.appendRow(keys);
    sh.getRange(1, 1, 1, keys.length).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  sh.appendRow(keys.map(function (k) { return row[k]; }));
}

function notify_(row) {
  var subject = '【働き方4.0診断】' + row.会社名 + '（' + row.お名前 + '様）';
  var text = [
    '働き方4.0診断の申し込みが届きました。', '',
    '■ 会社名：' + row.会社名,
    '■ お名前：' + row.お名前,
    '■ メール：' + row.メール,
    '■ 従業員数：' + row.従業員数,
    '■ いま困っていること：', (row.困っていること || '（未記入）'), '',
    '受信日時：' + Utilities.formatDate(row.受信日時, 'Asia/Tokyo', 'yyyy/MM/dd HH:mm'),
    '送信元：' + row.送信元
  ].join('\n');
  MailApp.sendEmail({ to: NOTIFY_TO, replyTo: row.メール, subject: subject, body: text });
}

function s_(v) { return String(v == null ? '' : v).trim().slice(0, 2000); }
function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
