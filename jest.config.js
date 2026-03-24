/** @type {import('jest').Config} */
module.exports = {
  testMatch: ["**/tests/unit/**/*.test.js"],
  collectCoverageFrom: ["scripts/js/**/*.js"],
  coverageDirectory: "coverage/jest",
};
