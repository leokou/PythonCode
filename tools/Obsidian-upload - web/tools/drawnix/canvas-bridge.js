/*
 * LeoDiary Capture → Drawnix 画布导入桥接
 *
 * Drawnix 用 localforage(IndexedDB，库名 Drawnix，store 名 drawnix_store) 持久化
 * 画布内容，键 main_board_content。localforage 的 IndexedDB driver 直接存取 JS 对象
 * （不经 JSON 序列化），因此本脚本也用原生 IndexedDB 写入对象。
 * 每 2 秒轮询 /api/import（canvas_server 提供），拿到待导入的内容后：
 *   1. markdown 类型：动态 import Drawnix 官方解析器（assets/dist-CikEzr4-.js），
 *      用 parseMarkdownToDrawnix 生成与 Drawnix 自身一致的思维导图元素；
 *      其他类型：直接作为画布 board 数据；
 *   2. 写入 main_board_content（对象）；
 *   3. location.reload() 让 Drawnix 重新从持久化读取，展示导入的思维导图。
 * 数据为一次性消费（服务端取走后清空），reload 后不会再触发。
 */
(function () {
  "use strict";
  var DB_NAME = "Drawnix";
  var STORE_NAME = "drawnix_store";
  var CONTENT_KEY = "main_board_content";
  var POLL_INTERVAL = 2000;

  function writeBoard(data) {
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME);
      req.onerror = function () { reject(req.error); };
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME);
        }
      };
      req.onsuccess = function () {
        var db = req.result;
        try {
          var tx = db.transaction(STORE_NAME, "readwrite");
          var store = tx.objectStore(STORE_NAME);
          // 关键：localforage 的 IndexedDB driver 直接存取 JS 对象（不经 JSON 序列化），
          // 必须存对象而非 JSON 字符串，否则 Drawnix 读回字符串后 e.children 为 undefined 崩溃。
          store.put(data, CONTENT_KEY);
          tx.oncomplete = function () { db.close(); resolve(); };
          tx.onerror = function () { db.close(); reject(tx.error); };
        } catch (e) {
          db.close();
          reject(e);
        }
      };
    });
  }

  /* Markdown → Drawnix 思维导图：复用 Drawnix 官方 parseMarkdownToDrawnix，
   * 保证生成的 mind 节点结构与 Drawnix 自身写入的一致，避免白屏。 */
  function buildBoardFromMarkdown(md) {
    return import("/assets/dist-CikEzr4-.js")
      .then(function (mod) {
        var el = mod.parseMarkdownToDrawnix(md);
        if (!el || !el.id) {
          throw new Error("parseMarkdownToDrawnix returned invalid element");
        }
        el.points = [[0, 0]];
        return {
          children: [el],
          viewport: { zoom: 1 },
          theme: { themeColorMode: "default" },
        };
      });
  }

  function poll() {
    fetch("/api/import", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (!res || !res.data) {
          return;
        }
        var payload = res.data;
        var build = (payload && payload.markdown !== undefined)
          ? buildBoardFromMarkdown(payload.markdown)
          : Promise.resolve(payload);
        return build.then(function (board) {
          return writeBoard(board).then(function () {
            location.reload();
          });
        });
      })
      .catch(function () {})
      .then(function () {
        setTimeout(poll, POLL_INTERVAL);
      });
  }

  if (typeof indexedDB === "undefined") {
    return;
  }
  setTimeout(poll, 800);
})();
