import { test, expect, Page } from '@playwright/test';

// Test fixtures and utilities
class RulesPage {
  constructor(public readonly page: Page) {}

  async goto() {
    await this.page.goto('/rules/editor');
  }

  async gotoAnalytics() {
    await this.page.goto('/rules/analytics');
  }

  async waitForMonacoEditor() {
    // Wait for Monaco editor to load
    await this.page.waitForSelector('.monaco-editor', { timeout: 10000 });
    await this.page.waitForFunction(() => {
      const editor = document.querySelector('.monaco-editor');
      return editor && editor.classList.contains('vs-dark');
    });
  }

  async setYamlContent(content: string) {
    await this.waitForMonacoEditor();
    // Clear existing content and type new content
    await this.page.keyboard.press('Control+a');
    await this.page.keyboard.type(content);
    // Wait for validation to complete
    await this.page.waitForTimeout(1000);
  }

  async getYamlContent(): Promise<string> {
    await this.waitForMonacoEditor();
    return await this.page.evaluate(() => {
      // Get Monaco editor instance
      const editorElement = document.querySelector('.monaco-editor');
      if (editorElement && (window as any).monaco) {
        const editor = (window as any).monaco.editor.getEditors()[0];
        return editor?.getValue() || '';
      }
      return '';
    });
  }

  async saveRule() {
    await this.page.click('button:has-text("Save Rule")');
  }

  async testRule() {
    await this.page.click('button:has-text("Test Rule")');
  }

  async importRule() {
    await this.page.click('button:has-text("Import")');
  }

  async exportRule() {
    await this.page.click('button:has-text("Export")');
  }

  async switchToPreviewMode() {
    await this.page.click('button[aria-label="Preview mode"]');
  }

  async switchToEditorMode() {
    await this.page.click('button[aria-label="Editor mode"]');
  }

  async switchToSplitMode() {
    await this.page.click('button[aria-label="Split mode"]');
  }

  async getValidationErrors() {
    const errorCard = this.page.locator('.border-destructive');
    if (await errorCard.count() > 0) {
      return await errorCard.locator('li').allTextContents();
    }
    return [];
  }

  async waitForEngineStatus(status: 'online' | 'offline') {
    await this.page.waitForSelector(`.status-indicator.${status}`, { timeout: 5000 });
  }

  // Rule Builder specific methods
  async addNewRule() {
    await this.page.click('button:has-text("Add Rule")');
  }

  async deleteRule(index: number) {
    const ruleItems = this.page.locator('[data-testid="rule-item"]');
    await ruleItems.nth(index).locator('button:has(svg[data-testid="trash-icon"])').click();
  }

  async duplicateRule(index: number) {
    const ruleItems = this.page.locator('[data-testid="rule-item"]');
    await ruleItems.nth(index).locator('button:has(svg[data-testid="copy-icon"])').click();
  }

  async dragRuleToPosition(fromIndex: number, toIndex: number) {
    const ruleItems = this.page.locator('[data-testid="rule-item"]');
    const source = ruleItems.nth(fromIndex);
    const target = ruleItems.nth(toIndex);
    
    await source.dragTo(target);
  }

  async openTemplateLibrary() {
    await this.page.click('button:has-text("Templates")');
  }

  async selectTemplate(templateName: string) {
    await this.page.click(`[data-testid="template-${templateName}"]`);
  }

  async updateRuleSetInfo(name: string, version: string, description?: string) {
    await this.page.fill('input[placeholder*="name"]', name);
    await this.page.fill('input[placeholder*="version"]', version);
    if (description) {
      await this.page.fill('textarea[placeholder*="description"]', description);
    }
  }
}

const SAMPLE_VALID_YAML = `name: "Test Rule Set"
version: "1.0.0"
description: "E2E test rule set"

fields:
  - name: "title"
    type: "string"
    required: true
  - name: "price"
    type: "number"
    required: true

rules:
  - id: "title_required"
    field: "title"
    type: "required"
    condition: "value != null"
    message: "Title is required"
    severity: "error"
    enabled: true`;

const INVALID_YAML = `name: "Invalid Rule Set"
version: 1.0.0  # Should be string
description: Test rule set

fields:
  - name: title
    type: invalid_type  # Invalid field type
    required: true

rules:
  - id: missing_field_rule
    # Missing required field
    type: "required"
    condition: "value != null"
    message: "Field is required"
    severity: "error"
    enabled: true`;

test.describe('Rules Editor', () => {
  let rulesPage: RulesPage;

  test.beforeEach(async ({ page }) => {
    rulesPage = new RulesPage(page);
    await rulesPage.goto();
  });

  test('should load the Monaco editor successfully', async () => {
    await expect(rulesPage.page.locator('.monaco-editor')).toBeVisible();
    await expect(rulesPage.page.locator('h1:has-text("Rule Editor")')).toBeVisible();
    
    // Check that default sample content is loaded
    const content = await rulesPage.getYamlContent();
    expect(content).toContain('E-commerce Product Validation');
  });

  test('should validate YAML syntax in real-time', async () => {
    // Test valid YAML
    await rulesPage.setYamlContent(SAMPLE_VALID_YAML);
    
    // Should show no validation errors
    const errors = await rulesPage.getValidationErrors();
    expect(errors).toHaveLength(0);
    
    // Should show green checkmark in preview
    await expect(rulesPage.page.locator('.text-green-500')).toBeVisible();
  });

  test('should show validation errors for invalid YAML', async () => {
    await rulesPage.setYamlContent(INVALID_YAML);
    
    // Should show validation errors
    const errors = await rulesPage.getValidationErrors();
    expect(errors.length).toBeGreaterThan(0);
    expect(errors.some(error => error.includes('field is required'))).toBeTruthy();
  });

  test('should switch between editor modes', async ({ page }) => {
    // Start in split mode (default)
    await expect(page.locator('.monaco-editor')).toBeVisible();
    await expect(page.locator('[data-testid="rule-preview"]')).toBeVisible();
    
    // Switch to editor only
    await rulesPage.switchToEditorMode();
    await expect(page.locator('.monaco-editor')).toBeVisible();
    await expect(page.locator('[data-testid="rule-preview"]')).not.toBeVisible();
    
    // Switch to preview only
    await rulesPage.switchToPreviewMode();
    await expect(page.locator('.monaco-editor')).not.toBeVisible();
    await expect(page.locator('[data-testid="rule-preview"]')).toBeVisible();
    
    // Switch back to split
    await rulesPage.switchToSplitMode();
    await expect(page.locator('.monaco-editor')).toBeVisible();
    await expect(page.locator('[data-testid="rule-preview"]')).toBeVisible();
  });

  test('should save rules successfully', async ({ page }) => {
    await rulesPage.setYamlContent(SAMPLE_VALID_YAML);
    
    // Mock the save API
    await page.route('/api/rules', async route => {
      expect(route.request().method()).toBe('POST');
      const postData = JSON.parse(route.request().postData() || '{}');
      expect(postData.name).toBe('Test Rule Set');
      expect(postData.version).toBe('1.0.0');
      
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, id: 'rule-123' }),
      });
    });
    
    await rulesPage.saveRule();
    
    // Should show success indication (this would come via SSE in real implementation)
    await expect(page.locator('button:has-text("Save Rule")')).not.toHaveAttribute('disabled');
  });

  test('should test rules with sample data', async ({ page }) => {
    await rulesPage.setYamlContent(SAMPLE_VALID_YAML);
    
    // Mock the test API
    await page.route('/api/rules/test', async route => {
      expect(route.request().method()).toBe('POST');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ 
          job_id: 'test-123',
          status: 'running' 
        }),
      });
    });
    
    await rulesPage.testRule();
    await expect(page.locator('button:has-text("Testing...")')).toBeVisible();
  });

  test('should import and export YAML files', async ({ page }) => {
    // Test export
    const downloadPromise = page.waitForEvent('download');
    await rulesPage.exportRule();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/\.yaml$/);
    
    // Test import (mock file selection)
    const fileChooserPromise = page.waitForEvent('filechooser');
    await rulesPage.importRule();
    const fileChooser = await fileChooserPromise;
    
    // Create a mock file
    const buffer = Buffer.from(SAMPLE_VALID_YAML);
    await fileChooser.setFiles([{
      name: 'test-rule.yaml',
      mimeType: 'application/x-yaml',
      buffer,
    }]);
    
    // Content should be updated
    await rulesPage.page.waitForTimeout(500);
    const content = await rulesPage.getYamlContent();
    expect(content).toContain('Test Rule Set');
  });
});

test.describe('Visual Rule Builder', () => {
  let rulesPage: RulesPage;

  test.beforeEach(async ({ page }) => {
    rulesPage = new RulesPage(page);
    // Navigate to a page that includes the RuleBuilder component
    await page.goto('/rules/builder');
  });

  test('should add new rules via drag and drop interface', async ({ page }) => {
    const initialRuleCount = await page.locator('[data-testid="rule-item"]').count();
    
    await rulesPage.addNewRule();
    
    const newRuleCount = await page.locator('[data-testid="rule-item"]').count();
    expect(newRuleCount).toBe(initialRuleCount + 1);
    
    // Should show the new rule with default values
    await expect(page.locator('[data-testid="rule-item"]').last()).toContainText('new_field');
  });

  test('should delete rules', async ({ page }) => {
    // Ensure we have at least one rule
    await rulesPage.addNewRule();
    
    const initialRuleCount = await page.locator('[data-testid="rule-item"]').count();
    await rulesPage.deleteRule(0);
    
    const newRuleCount = await page.locator('[data-testid="rule-item"]').count();
    expect(newRuleCount).toBe(initialRuleCount - 1);
  });

  test('should duplicate rules', async ({ page }) => {
    // Ensure we have at least one rule
    await rulesPage.addNewRule();
    
    const initialRuleCount = await page.locator('[data-testid="rule-item"]').count();
    await rulesPage.duplicateRule(0);
    
    const newRuleCount = await page.locator('[data-testid="rule-item"]').count();
    expect(newRuleCount).toBe(initialRuleCount + 1);
  });

  test('should reorder rules via drag and drop', async ({ page }) => {
    // Add multiple rules
    await rulesPage.addNewRule();
    await rulesPage.addNewRule();
    
    const ruleItems = page.locator('[data-testid="rule-item"]');
    await expect(ruleItems).toHaveCount(2);
    
    // Get text of first rule before drag
    const firstRuleText = await ruleItems.first().textContent();
    
    // Drag first rule to second position
    await rulesPage.dragRuleToPosition(0, 1);
    
    // First rule should now be in second position
    const secondRuleText = await ruleItems.nth(1).textContent();
    expect(secondRuleText).toBe(firstRuleText);
  });

  test('should apply templates from library', async ({ page }) => {
    await rulesPage.openTemplateLibrary();
    
    // Should show template library
    await expect(page.locator('h3:has-text("Template Library")')).toBeVisible();
    
    // Mock available templates
    await page.route('/api/rules/templates', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          {
            id: 'ecommerce-basic',
            name: 'E-commerce Basic',
            description: 'Basic product validation rules',
            category: 'ecommerce',
            template: {
              name: 'E-commerce Basic Rules',
              rules: [
                {
                  id: 'title_required',
                  field: 'title',
                  type: 'required',
                  message: 'Product title is required',
                  severity: 'error',
                  enabled: true,
                }
              ]
            }
          }
        ]),
      });
    });
    
    await rulesPage.selectTemplate('ecommerce-basic');
    
    // Should apply template and update rule set
    await expect(page.locator('[data-testid="rule-item"]')).toContainText('title');
  });

  test('should update rule set metadata', async ({ page }) => {
    await rulesPage.updateRuleSetInfo(
      'Custom Test Rules',
      '2.1.0',
      'Custom description for testing'
    );
    
    // Values should be updated in the form
    await expect(page.locator('input[placeholder*="name"]')).toHaveValue('Custom Test Rules');
    await expect(page.locator('input[placeholder*="version"]')).toHaveValue('2.1.0');
    await expect(page.locator('textarea[placeholder*="description"]')).toHaveValue('Custom description for testing');
  });
});

test.describe('Analytics Dashboard', () => {
  let rulesPage: RulesPage;

  test.beforeEach(async ({ page }) => {
    rulesPage = new RulesPage(page);
    await rulesPage.gotoAnalytics();
  });

  test('should load analytics dashboard with metrics', async ({ page }) => {
    await expect(page.locator('h1:has-text("Rules Analytics")')).toBeVisible();
    
    // Should show metric cards
    await expect(page.locator('[data-testid="metric-card"]')).toHaveCount(6);
    
    // Should show charts
    await expect(page.locator('canvas')).toHaveCount(4); // Line, Bar, Doughnut, and activity chart
  });

  test('should switch time ranges', async ({ page }) => {
    // Test time range buttons
    const timeRanges = ['Hour', 'Day', 'Week', 'Month'];
    
    for (const range of timeRanges) {
      await page.click(`button:has-text("${range}")`);
      await expect(page.locator(`button:has-text("${range}")`)).toHaveClass(/bg-primary/);
      
      // Charts should update (we can't test actual data changes in e2e, but can test UI updates)
      await page.waitForTimeout(500);
    }
  });

  test('should show real-time engine status', async ({ page }) => {
    // Mock SSE connection for engine status
    await page.addInitScript(() => {
      // Mock EventSource for engine status
      class MockEventSource extends EventTarget {
        readyState = 1; // OPEN
        url: string;
        
        constructor(url: string) {
          super();
          this.url = url;
          
          // Simulate initial connection
          setTimeout(() => {
            this.dispatchEvent(new MessageEvent('open', {}));
          }, 100);
          
          // Simulate status updates
          setTimeout(() => {
            const statusData = {
              connected: true,
              last_heartbeat: new Date().toISOString(),
              active_validations: 3,
              queue_size: 12,
              processing_rate: 150,
            };
            
            this.dispatchEvent(new MessageEvent('message', {
              data: JSON.stringify({
                event: 'rule.engine.status',
                data: statusData,
                timestamp: new Date().toISOString(),
              }),
            }));
          }, 200);
        }
        
        close() {
          this.readyState = 2; // CLOSED
        }
      }
      
      (window as any).EventSource = MockEventSource;
    });
    
    await rulesPage.waitForEngineStatus('online');
    
    // Should show engine status card
    await expect(page.locator('.status-indicator.online')).toBeVisible();
    await expect(page.locator('text=Engine Online')).toBeVisible();
  });

  test('should export analytics data', async ({ page }) => {
    const downloadPromise = page.waitForEvent('download');
    await page.click('button:has-text("Export")');
    
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/rules-analytics.*\.csv$/);
  });

  test('should show real-time validation activity', async ({ page }) => {
    // Should show activity feed
    await expect(page.locator('h4:has-text("Real-time Activity")')).toBeVisible();
    
    // Should show activity items (mocked data)
    const activityItems = page.locator('[data-testid="activity-item"]');
    await expect(activityItems).toHaveCount.toBeGreaterThan(0);
    
    // Each activity item should have timestamp and metrics
    const firstItem = activityItems.first();
    await expect(firstItem).toContainText('validations');
    await expect(firstItem).toContainText('success rate');
  });

  test('should handle connection failures gracefully', async ({ page }) => {
    // Mock failed SSE connection
    await page.addInitScript(() => {
      class FailingEventSource extends EventTarget {
        readyState = 2; // CLOSED
        
        constructor() {
          super();
          setTimeout(() => {
            this.dispatchEvent(new Event('error'));
          }, 100);
        }
        
        close() {}
      }
      
      (window as any).EventSource = FailingEventSource;
    });
    
    await rulesPage.gotoAnalytics();
    await rulesPage.waitForEngineStatus('offline');
    
    // Should show offline status
    await expect(page.locator('.status-indicator.offline')).toBeVisible();
    await expect(page.locator('text=Engine Offline')).toBeVisible();
  });
});

test.describe('End-to-End Rule Workflow', () => {
  let rulesPage: RulesPage;

  test('should complete full rule creation and testing workflow', async ({ page }) => {
    rulesPage = new RulesPage(page);
    
    // Step 1: Create rule in editor
    await rulesPage.goto();
    await rulesPage.setYamlContent(SAMPLE_VALID_YAML);
    
    // Verify no validation errors
    const errors = await rulesPage.getValidationErrors();
    expect(errors).toHaveLength(0);
    
    // Step 2: Save the rule
    await page.route('/api/rules', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, id: 'rule-e2e-123' }),
      });
    });
    
    await rulesPage.saveRule();
    
    // Step 3: Test the rule
    await page.route('/api/rules/test', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ 
          job_id: 'test-e2e-123',
          status: 'completed',
          results: {
            total_rows: 100,
            processed_rows: 100,
            errors: 2,
            warnings: 5,
            success_rate: 93,
          }
        }),
      });
    });
    
    await rulesPage.testRule();
    
    // Step 4: View results in analytics
    await rulesPage.gotoAnalytics();
    await expect(page.locator('h1:has-text("Rules Analytics")')).toBeVisible();
    
    // Should show the test results
    await expect(page.locator('[data-testid="metric-card"]')).toHaveCount(6);
  });
});

test.describe('Accessibility', () => {
  test('should be keyboard navigable', async ({ page }) => {
    await page.goto('/rules/editor');
    
    // Tab through the interface
    await page.keyboard.press('Tab'); // Should focus first interactive element
    await page.keyboard.press('Tab'); // Save button
    await page.keyboard.press('Tab'); // Test button
    await page.keyboard.press('Tab'); // Import button
    await page.keyboard.press('Tab'); // Export button
    
    // Should be able to activate buttons with keyboard
    await page.keyboard.press('Enter');
  });

  test('should have proper ARIA labels', async ({ page }) => {
    await page.goto('/rules/editor');
    
    // Check for important ARIA labels
    await expect(page.locator('button[aria-label*="Save"]')).toBeVisible();
    await expect(page.locator('button[aria-label*="Test"]')).toBeVisible();
    await expect(page.locator('[role="textbox"]')).toBeVisible(); // Monaco editor
  });

  test('should support screen readers', async ({ page }) => {
    await page.goto('/rules/analytics');
    
    // Check for semantic HTML and labels
    await expect(page.locator('h1')).toHaveCount(1);
    await expect(page.locator('main, [role="main"]')).toBeVisible();
    await expect(page.locator('[aria-live="polite"]')).toBeVisible(); // For real-time updates
  });
});