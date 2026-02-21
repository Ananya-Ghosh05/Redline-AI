/**
 * Entry point – starts the Express server and initialises the database.
 */
const app = require("./app");
const db = require("./db");
const config = require("./config");

async function main() {
  try {
    await db.initializeDatabase();
    console.log("Database initialised.");
  } catch (err) {
    console.warn(
      "Database initialisation skipped (connection may not be available):",
      err.message
    );
  }

  app.listen(config.port, () => {
    console.log(`Redline AI IVR server listening on port ${config.port}`);
  });
}

main();
