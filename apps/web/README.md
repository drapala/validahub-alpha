# Smart Rules Engine - Frontend

A modern Next.js 15 application for building, testing, and managing CSV validation rules with real-time analytics and visual rule building capabilities.

## Features

### 🎨 Visual Rule Editor
- **Monaco Editor Integration**: Professional YAML editing with syntax highlighting, autocomplete, and real-time validation
- **Multiple View Modes**: Switch between editor, preview, and split view modes
- **Real-time Validation**: Instant feedback on rule syntax and semantics
- **Import/Export**: Import and export rule sets as YAML files

### 🧩 Drag-and-Drop Rule Builder  
- **Visual Interface**: Build complex validation rules without writing code
- **Sortable Rules**: Reorder rules with drag-and-drop functionality
- **Template Library**: Pre-built rule templates for common use cases
- **Rule Management**: Add, edit, duplicate, and delete rules visually

### 📊 Real-time Analytics Dashboard
- **Live Metrics**: Server-sent events for real-time validation statistics
- **Interactive Charts**: Line charts, bar charts, and doughnut charts powered by Chart.js
- **Performance Insights**: Processing time, success rates, and error analytics
- **Data Export**: Export analytics data as CSV files

### ⚡ Real-time Features
- **Server-Sent Events**: Live updates for validation results and engine status
- **Smart Suggestions**: AI-powered rule optimization recommendations
- **Instant Notifications**: Real-time alerts for validation events
- **Connection Status**: Live engine connection monitoring

## Technology Stack

- **Framework**: Next.js 15 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Components**: shadcn/ui + Radix UI
- **Editor**: Monaco Editor (VS Code editor)
- **Charts**: Chart.js with react-chartjs-2
- **Drag & Drop**: @dnd-kit/core
- **Real-time**: Server-Sent Events (SSE)
- **Testing**: Playwright for E2E testing
- **Build Tool**: Next.js built-in bundling

## Project Structure

```
apps/web/
├── app/                          # Next.js App Router
│   ├── globals.css              # Global styles and CSS variables
│   ├── layout.tsx               # Root layout component
│   ├── page.tsx                 # Homepage with feature overview
│   └── rules/                   # Rules management routes
│       ├── analytics/           # Analytics dashboard
│       ├── builder/             # Visual rule builder
│       └── editor/              # Monaco editor
├── components/                   # React components
│   ├── ui/                      # shadcn/ui components
│   └── RuleBuilder.tsx          # Visual rule builder component
├── lib/                         # Utility libraries
│   ├── utils.ts                # Common utilities
│   └── rules/
│       └── sse-client.ts       # Server-Sent Events client
├── types/                       # TypeScript type definitions
│   └── rules.ts                # Rules engine types
└── tests/                       # Test suites
    └── e2e/                    # Playwright E2E tests
        └── rules.spec.ts       # Rules functionality tests
```

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Running ValidaHub backend API (for SSE and data persistence)

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start
```

### Development

```bash
# Run development server with hot reload
npm run dev

# Run linting
npm run lint

# Run E2E tests
npm run test:e2e

# Run E2E tests with UI
npm run test:e2e:ui
```

The application will be available at `http://localhost:3000`.

## Key Components

### Monaco Editor Integration

The rule editor uses Monaco Editor for professional YAML editing:

```tsx
import Editor from '@monaco-editor/react';

<Editor
  height="600px"
  language="yaml"
  theme="vs-dark"
  value={yamlContent}
  onChange={handleEditorChange}
  options={{
    minimap: { enabled: true },
    fontSize: 14,
    wordWrap: 'on',
    bracketPairColorization: { enabled: true },
  }}
/>
```

### Server-Sent Events Client

Real-time updates are powered by a custom SSE client:

```tsx
import { useRuleEngineStatus, useValidationResults } from '@/lib/rules/sse-client';

const { data: engineStatus, connected } = useRuleEngineStatus();
const { data: validationResult } = useValidationResults(jobId);
```

### Drag-and-Drop Rule Builder

Visual rule building uses @dnd-kit for smooth drag-and-drop:

```tsx
import { DndContext, DragEndEvent } from '@dnd-kit/core';
import { SortableContext, useSortable } from '@dnd-kit/sortable';

<DndContext onDragEnd={handleDragEnd}>
  <SortableContext items={rules}>
    {rules.map(rule => <DraggableRule key={rule.id} rule={rule} />)}
  </SortableContext>
</DndContext>
```

## API Integration

The frontend communicates with the ValidaHub backend API:

- **Rules CRUD**: `/api/rules` - Create, read, update, delete rule sets
- **Validation**: `/api/rules/validate` - Test rules with sample data  
- **SSE Streams**: `/api/rules/*/stream` - Real-time event streams
- **Templates**: `/api/rules/templates` - Rule template library

### SSE Endpoints

- `/api/rules/validation/stream` - Validation results
- `/api/rules/engine/status/stream` - Engine status updates
- `/api/rules/suggestions/stream` - Smart suggestions
- `/api/rules/analytics/stream` - Analytics metrics

## Testing

### E2E Testing with Playwright

Comprehensive E2E tests cover the complete user workflow:

```bash
# Run all E2E tests
npm run test:e2e

# Run tests with browser UI
npm run test:e2e:ui

# Run specific test file
npx playwright test rules.spec.ts
```

Test scenarios include:
- Monaco editor functionality
- Rule validation and error handling
- Drag-and-drop rule building
- Real-time analytics updates
- Import/export workflows
- Accessibility compliance

### Test Structure

```typescript
test.describe('Rules Editor', () => {
  test('should validate YAML syntax in real-time', async ({ page }) => {
    const rulesPage = new RulesPage(page);
    await rulesPage.setYamlContent(SAMPLE_VALID_YAML);
    
    const errors = await rulesPage.getValidationErrors();
    expect(errors).toHaveLength(0);
  });
});
```

## Performance Optimizations

- **Code Splitting**: Automatic route-based code splitting
- **Monaco Loading**: Lazy load Monaco editor to reduce initial bundle
- **SSE Management**: Efficient connection pooling and cleanup
- **Chart Optimization**: Virtualized charts for large datasets
- **Image Optimization**: Next.js automatic image optimization

## Accessibility Features

- **Keyboard Navigation**: Full keyboard support for all interactions
- **Screen Reader Support**: Proper ARIA labels and semantic HTML
- **High Contrast**: Support for high contrast themes
- **Focus Management**: Proper focus indicators and management
- **Responsive Design**: Works on all screen sizes and devices

## Environment Variables

```env
# Development
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000

# Production
NEXT_PUBLIC_API_URL=https://api.validahub.com
NEXT_PUBLIC_WS_URL=wss://api.validahub.com
```

## Deployment

### Vercel (Recommended)

```bash
# Connect to Vercel
vercel

# Deploy
vercel --prod
```

### Docker

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

### Build Output

The production build creates:
- Static assets in `.next/static/`
- Server-side code in `.next/server/`
- Optimized images and fonts

## Browser Support

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feat/smart-rules-ui`
3. Make changes following the established patterns
4. Add tests for new functionality
5. Run E2E tests: `npm run test:e2e`
6. Submit pull request

### Code Style

- Use TypeScript for all components
- Follow shadcn/ui patterns for components
- Use Tailwind CSS for styling
- Add proper JSDoc comments for public APIs
- Ensure accessibility compliance

## License

This project is part of ValidaHub and follows the same licensing terms.