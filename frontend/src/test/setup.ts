// Runs once before every Vitest test file.
// Imports @testing-library/jest-dom so we get matchers like:
//   expect(button).toBeInTheDocument()
//   expect(input).toHaveValue("foo")
import '@testing-library/jest-dom/vitest'
