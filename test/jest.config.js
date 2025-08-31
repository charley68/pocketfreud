module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterEnv: ['./tests/jest.setup.js'],
  moduleNameMapper: {
    '\\.(css|less|scss|sass)$': '<rootDir>/tests/styleMock.js'
  },
  testMatch: [
    '**/tests/**/*.test.js'
  ]
};
