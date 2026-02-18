require("dotenv").config();

module.exports = {
  port: process.env.PORT || 3000,
  database: {
    connectionString:
      process.env.DATABASE_URL ||
      "postgresql://user:password@localhost:5432/redline_ai",
  },
  twilio: {
    accountSid: process.env.TWILIO_ACCOUNT_SID,
    authToken: process.env.TWILIO_AUTH_TOKEN,
    phoneNumber: process.env.TWILIO_PHONE_NUMBER,
  },
  google: {
    projectId: process.env.GOOGLE_PROJECT_ID,
    credentials: process.env.GOOGLE_APPLICATION_CREDENTIALS,
  },
};
