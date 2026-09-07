/**
 * 働き方4.0 LP / AIブートキャンプ — 問い合わせフォームの受け口（Google Apps Script / ウェブアプリ）
 *
 * 1 つのデプロイを両方のページで共用する。どのページから届いたかは body.source で判定し、
 *   - 「問い合わせ」シート … 全件（先頭列に流入元）
 *   - 「LP」「ブートキャンプ」シート … 流入元ごとの一覧
 * の両方に 1 行ずつ追記し、通知メールの件名も流入元で変える。
 *
 * このスクリプトは「スプレッドシートに紐づいたプロジェクト」に貼る前提。
 *
 * デプロイ: デプロイ > 新しいデプロイ > 種類「ウェブアプリ」
 *   次のユーザーとして実行: 自分
 *   アクセスできるユーザー: 全員
 * → 表示された「ウェブアプリの URL（…/exec）」を両ページの GAS_URL に設定する。
 *
 * ページ側は Content-Type を付けずに JSON 文字列を POST する（ブラウザの CORS 事前確認を
 * 発生させないため）。ここでは postData.contents を JSON として読む。
 */

var NOTIFY_TO = 'm.gomita@canvas-sr.jp';   // 通知先
var ALL_SHEET = '問い合わせ';                // 全件シート

// 流入元の定義。key はページ側の payload.source。無いときは page の URL から推定する。
var SOURCES = {
  lp:       { label: 'LP',           sheet: 'LP',           subject: '【働き方4.0診断】', lead: '働き方4.0診断の申し込みが届きました。' },
  bootcamp: { label: 'ブートキャンプ', sheet: 'ブートキャンプ', subject: '【ブートキャンプ申込】', lead: 'AIブートキャンプの受講申し込みが届きました。' }
};

function doPost(e) {
  var out = { ok: false };
  try {
    var body = {};
    try { body = JSON.parse((e && e.postData && e.postData.contents) || '{}'); } catch (err) { body = (e && e.parameter) || {}; }

    // 迷惑投稿対策: 隠し欄が埋まっていたら黙って成功扱いにして捨てる
    if (body._honey) { out.ok = true; return json_(out); }

    var src = source_(body);
    var row = {
      受信日時: new Date(),
      流入元: src.label,
      会社名: s_(body.company),
      お名前: s_(body.name),
      メール: s_(body.email),
      従業員数: s_(body.size),
      困っていること: s_(body.msg),
      送信元URL: s_(body.page || ''),
      参照元: s_(body.ref || ''),
      UA: s_(body.ua || '')
    };
    if (!row.会社名 || !row.お名前 || !row.メール) { out.error = 'required'; return json_(out); }

    appendRow_(ALL_SHEET, row);
    appendRow_(src.sheet, row);
    notify_(row, src);
    out.ok = true;
  } catch (err) {
    out.error = String(err && err.message || err);
  }
  return json_(out);
}

// 動作確認用: ブラウザで /exec を開くと ok が返る
function doGet() { return json_({ ok: true, service: 'relic inquiry', sources: Object.keys(SOURCES) }); }

function source_(body) {
  var k = String(body.source || '').toLowerCase();
  if (!SOURCES[k]) k = /bootcamp/i.test(String(body.page || '')) ? 'bootcamp' : 'lp';
  return SOURCES[k];
}

function appendRow_(name, row) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(name) || ss.insertSheet(name);
  var keys = Object.keys(row);
  if (sh.getLastRow() === 0) {
    sh.appendRow(keys);
    sh.getRange(1, 1, 1, keys.length).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  sh.appendRow(keys.map(function (k) { return row[k]; }));
}

function notify_(row, src) {
  var subject = src.subject + row.会社名 + '（' + row.お名前 + '様）';
  var text = [
    src.lead, '',
    '■ 流入元：' + row.流入元,
    '■ 会社名：' + row.会社名,
    '■ お名前：' + row.お名前,
    '■ メール：' + row.メール,
    '■ 従業員数：' + row.従業員数,
    '■ いま困っていること：', (row.困っていること || '（未記入）'), '',
    '受信日時：' + Utilities.formatDate(row.受信日時, 'Asia/Tokyo', 'yyyy/MM/dd HH:mm'),
    '送信元：' + row.送信元URL
  ].join('\n');
  MailApp.sendEmail({ to: NOTIFY_TO, replyTo: row.メール, subject: subject, body: text });
}

function s_(v) { return String(v == null ? '' : v).trim().slice(0, 2000); }
function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
