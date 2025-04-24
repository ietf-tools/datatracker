const { test, expect } = require('@playwright/test')
const viewports = require('../../helpers/viewports')
const { setTimeout } = require('timers/promises')

// ====================================================================
// ANNOUNCEMENT | DESKTOP viewport
// ====================================================================

test.describe('desktop', () => {
  
  test.beforeAll(async ({ browser }) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await page.goto('/accounts/login/');

    await page.fill('input#id_username', 'glen');
    await page.fill('input#id_password', 'password');

    await page.click('button[type="submit"]');
    await page.waitForURL('/accounts/profile/');

    await context.storageState({ path: 'auth.json' });

    await context.close();
  });

  test.beforeEach(async ({ browser }) => {
    // Reuse the authentication state in each test
    const context = await browser.newContext({ storageState: 'auth.json' });
    const page = await context.newPage();
    await page.setViewportSize({
      width: viewports.desktop[0],
      height: viewports.desktop[1]
    })
    await page.goto(`/secr/announcement/`); 
    await page.locator('h1:text("Announcement")').waitFor({ state: 'visible' })
    await setTimeout(500)
    // Attach the page to the test context
    test.info().page = page;
  })

  test('show to custom', async () => {
    const page = test.info().page;

    // to_custom should initially be hidden
    const element = page.locator('#id_to_custom');
    await expect(element).toBeHidden();
    await page.selectOption('select#id_to', 'Other...');
    await expect(element).toBeVisible();
  })

  test('back button', async () => {
    const page = test.info().page;

    const element = page.locator('#id_to_custom');
    await page.selectOption('select#id_to', 'Other...');
    await expect(element).toBeVisible();
    await page.fill('input#id_to_custom', 'custom@example.com');
    await page.selectOption('select#id_frm', 'IETF Chair <chair@ietf.org>');
    await page.fill('input#id_reply_to', 'greg@example.com');
    await page.fill('input#id_subject', 'About Stuff');
    await page.fill('textarea#id_body', 'This is the stuff');

    await page.click('text="Continue"');
    const h2Locator = page.locator('h2:text("Confirm Announcement")');
    await h2Locator.waitFor({ state: 'visible' });

    // click back button and check to_custom
    await page.click('text="Back"');
    const subjectLocator = page.locator('input#id_subject');
    await subjectLocator.waitFor({ state: 'visible' });
    await expect(element).toBeVisible();
    await expect(element).toHaveValue('custom@example.com');
  })

})