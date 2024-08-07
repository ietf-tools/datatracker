module.exports = {
  login: async (page, baseURL, username, password) => {
    await page.goto('/accounts/login/')
    await page.getByLabel('Username').fill(username)
    await page.getByLabel('Password').fill(password)
    await page.getByRole('button', { name: 'Sign in' }).click()
    // Wait until the page receives the cookies.
    //
    // Theoretically login flow could set cookies in the process of several
    // redirects.
    // Wait for the final URL to ensure that the cookies are actually set.
    await page.waitForURL(
      new URL('/accounts/profile/', baseURL).toString()
    )
  }
}
