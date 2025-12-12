const functions = require("firebase-functions");
const admin = require("firebase-admin");
admin.initializeApp();

const db = admin.firestore();

// ---- Config ----
const SECRET = functions.config().readcap?.secret || "";
const DAILY_CAP = parseInt(functions.config().readcap?.total_daily_cap || "200000", 10);
const TIMEZONE = functions.config().readcap?.timezone || "America/Los_Angeles";

// Helper: YYYY-MM-DD string in a specific TZ
function dateInTZ(tz) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" })
    .format(new Date());
}

// Usage doc for today
function usageRefForToday() {
  const today = dateInTZ(TIMEZONE); // e.g., 2025-08-12
  return db.collection("Usage").doc(today);
}

// Increment usage in a transaction; enforce cap
async function checkAndIncrement(readUnits) {
  await db.runTransaction(async (tx) => {
    const ref = usageRefForToday();
    const snap = await tx.get(ref);

    const current = snap.exists ? (snap.data().readCount || 0) : 0;
    const next = current + readUnits;

    if (next > DAILY_CAP) {
      throw new functions.https.HttpsError("resource-exhausted",
        `Daily read limit reached. Requested +${readUnits} would exceed cap ${DAILY_CAP}.`);
    }

    tx.set(ref, {
      date: ref.id,
      readCount: admin.firestore.FieldValue.increment(readUnits),
      updatedAt: admin.firestore.FieldValue.serverTimestamp()
    }, { merge: true });
  });
}

/**
 * Compute "read units" for billing approximation.
 * - Firestore charges at least 1 doc read per query even if 0 results.
 * - Exact index-entry reads are not exposed, so we cap by document reads.
 * - For a single doc get: 1
 * - For query: Math.max(1, number of docs returned)
 */
function computeReadUnits(docsReturned) {
  const n = typeof docsReturned === "number" ? docsReturned : 1;
  return Math.max(1, n);
}

/**
 * HTTPS proxy for reads:
 *  - Auth via header:  X-READCAP-SECRET: <SECRET>
 *  - Body format:
 *    { mode: "getDoc"|"query",
 *      collection: "Cities",
 *      docId?: "SF",
 *      where?: [{ field, op, value }], // for query
 *      orderBy?: [{ field, direction }], // optional
 *      limit?: number // optional
 *    }
 */
exports.limitedReadHttp = functions.https.onRequest(async (req, res) => {
  try {
    // Simple shared-secret auth
    const incoming = req.get("X-READCAP-SECRET") || "";
    if (!SECRET || incoming !== SECRET) {
      return res.status(401).json({ error: "Unauthorized" });
    }

    if (req.method !== "POST") {
      return res.status(405).json({ error: "Use POST" });
    }

    const { mode, collection, docId, where = [], orderBy = [], limit } = req.body || {};
    if (!mode || !collection) {
      return res.status(400).json({ error: "Missing 'mode' or 'collection'" });
    }

    let resultPayload = null;
    let docsReturned = 0;

    if (mode === "getDoc") {
      if (!docId) return res.status(400).json({ error: "Missing 'docId' for getDoc" });
      const snap = await db.collection(collection).doc(docId).get();
      docsReturned = snap.exists ? 1 : 0; // still counts as 1 read if queried
      await checkAndIncrement(computeReadUnits(docsReturned));
      resultPayload = snap.exists ? { id: snap.id, ...snap.data() } : null;

    } else if (mode === "query") {
      let q = db.collection(collection);
      // where: [{field, op, value}]
      where.forEach(w => { q = q.where(w.field, w.op, w.value); });

      // orderBy: [{field, direction}]
      orderBy.forEach(o => { q = q.orderBy(o.field, o.direction || "asc"); });

      if (limit && Number.isInteger(limit)) q = q.limit(limit);

      const qsnap = await q.get();
      docsReturned = qsnap.size;

      await checkAndIncrement(computeReadUnits(docsReturned));

      resultPayload = qsnap.docs.map(d => ({ id: d.id, ...d.data() }));
    } else {
      return res.status(400).json({ error: "Invalid 'mode'. Use 'getDoc' or 'query'." });
    }

    return res.json({
      ok: true,
      docsReturned,
      data: resultPayload
    });
  } catch (err) {
    const code = err?.code === "resource-exhausted" ? 429 : 500;
    return res.status(code).json({ error: err.message || "Internal error" });
  }
});

// Optional: callable for web/mobile Firebase client SDKs
exports.limitedReadCallable = functions.https.onCall(async (data, context) => {
  const { mode, collection, docId, where = [], orderBy = [], limit } = data || {};
  if (!mode || !collection) {
    throw new functions.https.HttpsError("invalid-argument", "Missing 'mode' or 'collection'");
  }

  // (Optional) enforce auth for callable
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "Sign-in required.");
  }

  if (mode === "getDoc") {
    if (!docId) throw new functions.https.HttpsError("invalid-argument", "Missing 'docId'");
    const snap = await db.collection(collection).doc(docId).get();
    const docsReturned = snap.exists ? 1 : 0;
    await checkAndIncrement(computeReadUnits(docsReturned));
    return { ok: true, docsReturned, data: snap.exists ? { id: snap.id, ...snap.data() } : null };
  }

  if (mode === "query") {
    let q = db.collection(collection);
    where.forEach(w => { q = q.where(w.field, w.op, w.value); });
    orderBy.forEach(o => { q = q.orderBy(o.field, o.direction || "asc"); });
    if (limit && Number.isInteger(limit)) q = q.limit(limit);

    const qsnap = await q.get();
    const docsReturned = qsnap.size;
    await checkAndIncrement(computeReadUnits(docsReturned));
    const dataOut = qsnap.docs.map(d => ({ id: d.id, ...d.data() }));
    return { ok: true, docsReturned, data: dataOut };
  }

  throw new functions.https.HttpsError("invalid-argument", "Invalid 'mode'");
});

// Reset usage daily at midnight Pacific Time
exports.resetDailyUsage = functions.pubsub
  .schedule("0 0 * * *")
  .timeZone(TIMEZONE)
  .onRun(async () => {
    const today = dateInTZ(TIMEZONE);
    // Remove all docs except today (optional: you can also leave history)
    const usageCol = db.collection("Usage");
    const snaps = await usageCol.get();
    const batch = db.batch();
    snaps.forEach(doc => {
      if (doc.id !== today) batch.delete(doc.ref);
    });
    await batch.commit();
    return null;
  });
