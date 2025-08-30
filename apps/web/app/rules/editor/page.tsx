'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useSSE, useRuleEngineStatus } from '@/lib/rules/sse-client';
import { parseYaml, stringifyYaml, validateRuleSchema, debounce } from '@/lib/utils';
import { RuleSet, ValidationResult } from '@/types/rules';
import { 
  Play, 
  Save, 
  Download, 
  Upload, 
  RefreshCw, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle,
  Eye,
  Code,
  Palette 
} from 'lucide-react';

const SAMPLE_RULE_YAML = `name: "E-commerce Product Validation"
version: "1.0.0"
description: "Comprehensive product data validation for e-commerce platforms"
marketplace: "mercado_livre"

fields:
  - name: "title"
    type: "string"
    required: true
    description: "Product title"
  - name: "price"
    type: "number"
    required: true
    description: "Product price"
  - name: "category"
    type: "string"
    required: true
    description: "Product category"
  - name: "description"
    type: "string"
    required: false
    description: "Product description"

rules:
  - id: "title_length"
    field: "title"
    type: "range"
    condition: "length >= 10 && length <= 200"
    message: "Product title must be between 10 and 200 characters"
    severity: "error"
    enabled: true
    
  - id: "price_positive"
    field: "price"
    type: "range"
    condition: "value > 0"
    message: "Product price must be positive"
    severity: "error"
    enabled: true
    
  - id: "category_format"
    field: "category"
    type: "pattern"
    condition: "^[A-Za-z][A-Za-z\\s]+$"
    message: "Category should contain only letters and spaces"
    severity: "warning"
    enabled: true

metadata:
  created_at: "${new Date().toISOString()}"
  updated_at: "${new Date().toISOString()}"
  created_by: "user@validahub.com"
  tags: ["e-commerce", "products", "validation"]
`;

interface ValidationError {
  line: number;
  column: number;
  message: string;
  severity: 'error' | 'warning' | 'info';
}

export default function RuleEditorPage() {
  const [yamlContent, setYamlContent] = useState(SAMPLE_RULE_YAML);
  const [validationErrors, setValidationErrors] = useState<ValidationError[]>([]);
  const [parseErrors, setParseErrors] = useState<string[]>([]);
  const [isValidating, setIsValidating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [previewMode, setPreviewMode] = useState<'editor' | 'preview' | 'split'>('split');
  const [ruleSet, setRuleSet] = useState<RuleSet | null>(null);
  
  const editorRef = useRef<any>(null);
  const { data: engineStatus, connected: engineConnected } = useRuleEngineStatus();
  const { data: validationResult } = useSSE<ValidationResult>('/api/rules/validation/stream');

  // Debounced validation
  const debouncedValidate = useCallback(
    debounce(async (content: string) => {
      try {
        setParseErrors([]);
        const parsed = parseYaml(content);
        const validation = validateRuleSchema(parsed);
        
        if (validation.valid) {
          setRuleSet(parsed);
          // Send for real-time validation via SSE
          await fetch('/api/rules/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rules: parsed }),
          });
        } else {
          setParseErrors(validation.errors);
          setRuleSet(null);
        }
      } catch (error) {
        setParseErrors([error instanceof Error ? error.message : 'Unknown parsing error']);
        setRuleSet(null);
      }
    }, 500),
    []
  );

  useEffect(() => {
    debouncedValidate(yamlContent);
  }, [yamlContent, debouncedValidate]);

  const handleEditorChange = (value: string | undefined) => {
    if (value !== undefined) {
      setYamlContent(value);
    }
  };

  const handleEditorMount = (editor: any, monaco: any) => {
    editorRef.current = editor;

    // Configure YAML language support
    monaco.languages.setMonarchTokensProvider('yaml', {
      tokenizer: {
        root: [
          [/^(\s*)([\w\-\s]+)(:)/, ['', 'key', 'delimiter']],
          [/^\s*-/, 'list.punctuation'],
          [/"([^"\\]|\\.)*$/, 'string.invalid'],
          [/'([^'\\]|\\.)*$/, 'string.invalid'],
          [/"/, 'string', '@doubleQuotedBody'],
          [/'/, 'string', '@singleQuotedBody'],
          [/[\[\]{}]/, 'delimiter.bracket'],
          [/[0-9]+/, 'number'],
          [/#.*$/, 'comment'],
        ],
        doubleQuotedBody: [
          [/[^\\"]+/, 'string'],
          [/\\./, 'string.escape'],
          [/"/, 'string', '@pop'],
        ],
        singleQuotedBody: [
          [/[^\\']+/, 'string'],
          [/\\./, 'string.escape'],
          [/'/, 'string', '@pop'],
        ],
      },
    });

    // Add real-time validation markers
    editor.onDidChangeModelContent(() => {
      // Clear existing markers
      monaco.editor.setModelMarkers(editor.getModel(), 'yaml-validation', []);
      
      // Add new markers based on validation errors
      if (validationErrors.length > 0) {
        const markers = validationErrors.map(error => ({
          startLineNumber: error.line,
          startColumn: error.column,
          endLineNumber: error.line,
          endColumn: error.column + 10,
          message: error.message,
          severity: error.severity === 'error' ? monaco.MarkerSeverity.Error : monaco.MarkerSeverity.Warning,
        }));
        monaco.editor.setModelMarkers(editor.getModel(), 'yaml-validation', markers);
      }
    });
  };

  const handleSaveRule = async () => {
    if (!ruleSet) return;
    
    setIsSaving(true);
    try {
      const response = await fetch('/api/rules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ruleSet),
      });
      
      if (response.ok) {
        // Success notification would be handled by SSE
      }
    } catch (error) {
      console.error('Failed to save rule:', error);
    } finally {
      setIsSaving(false);
    }
  };

  const handleTestRule = async () => {
    if (!ruleSet) return;
    
    setIsValidating(true);
    try {
      await fetch('/api/rules/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          rules: ruleSet,
          sample_data: [] // Would include sample CSV data
        }),
      });
    } catch (error) {
      console.error('Failed to test rule:', error);
    } finally {
      setIsValidating(false);
    }
  };

  const handleImportRule = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.yaml,.yml';
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
          const content = e.target?.result as string;
          setYamlContent(content);
        };
        reader.readAsText(file);
      }
    };
    input.click();
  };

  const handleExportRule = () => {
    const blob = new Blob([yamlContent], { type: 'application/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `rule-${ruleSet?.name || 'untitled'}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const renderPreview = () => {
    if (!ruleSet) return <div className="p-4 text-muted-foreground">Invalid YAML</div>;
    
    return (
      <div className="p-4 space-y-4">
        <div>
          <h3 className="font-semibold text-lg">{ruleSet.name}</h3>
          <p className="text-sm text-muted-foreground">{ruleSet.description}</p>
          <div className="flex gap-2 mt-2">
            <span className="px-2 py-1 bg-primary/10 text-primary text-xs rounded">
              v{ruleSet.version}
            </span>
            {ruleSet.marketplace && (
              <span className="px-2 py-1 bg-secondary text-secondary-foreground text-xs rounded">
                {ruleSet.marketplace}
              </span>
            )}
          </div>
        </div>
        
        <div>
          <h4 className="font-medium mb-2">Fields ({ruleSet.fields?.length || 0})</h4>
          <div className="space-y-2">
            {ruleSet.fields?.map((field, index) => (
              <div key={index} className="p-2 border rounded-md">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm">{field.name}</span>
                  <span className="text-xs text-muted-foreground">({field.type})</span>
                  {field.required && (
                    <span className="text-xs bg-red-100 text-red-800 px-1 rounded">required</span>
                  )}
                </div>
                {field.description && (
                  <p className="text-xs text-muted-foreground mt-1">{field.description}</p>
                )}
              </div>
            ))}
          </div>
        </div>
        
        <div>
          <h4 className="font-medium mb-2">Rules ({ruleSet.rules?.length || 0})</h4>
          <div className="space-y-2">
            {ruleSet.rules?.map((rule, index) => (
              <div key={index} className="p-2 border rounded-md">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-sm">{rule.field}</span>
                  <span className="text-xs text-muted-foreground">({rule.type})</span>
                  <span className={`text-xs px-1 rounded ${
                    rule.severity === 'error' ? 'bg-red-100 text-red-800' :
                    rule.severity === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-blue-100 text-blue-800'
                  }`}>
                    {rule.severity}
                  </span>
                </div>
                <p className="text-xs text-muted-foreground">{rule.message}</p>
                <code className="text-xs bg-muted p-1 rounded block mt-1">{rule.condition}</code>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Rule Editor</h1>
          <p className="text-muted-foreground">
            Create and edit validation rules with real-time preview and validation
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <div className={`status-indicator ${engineConnected ? 'online' : 'offline'}`}>
            <div className="pulse-dot"></div>
            Engine {engineConnected ? 'Online' : 'Offline'}
          </div>
          
          <div className="flex gap-1 border rounded-md">
            <Button
              variant={previewMode === 'editor' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setPreviewMode('editor')}
            >
              <Code className="h-4 w-4" />
            </Button>
            <Button
              variant={previewMode === 'split' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setPreviewMode('split')}
            >
              <Palette className="h-4 w-4" />
            </Button>
            <Button
              variant={previewMode === 'preview' ? 'default' : 'ghost'}
              size="sm"
              onClick={() => setPreviewMode('preview')}
            >
              <Eye className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        <Button onClick={handleSaveRule} disabled={!ruleSet || isSaving}>
          <Save className="h-4 w-4 mr-2" />
          {isSaving ? 'Saving...' : 'Save Rule'}
        </Button>
        <Button variant="outline" onClick={handleTestRule} disabled={!ruleSet || isValidating}>
          <Play className="h-4 w-4 mr-2" />
          {isValidating ? 'Testing...' : 'Test Rule'}
        </Button>
        <Button variant="outline" onClick={handleImportRule}>
          <Upload className="h-4 w-4 mr-2" />
          Import
        </Button>
        <Button variant="outline" onClick={handleExportRule} disabled={!ruleSet}>
          <Download className="h-4 w-4 mr-2" />
          Export
        </Button>
      </div>

      {parseErrors.length > 0 && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive flex items-center gap-2">
              <XCircle className="h-5 w-5" />
              Validation Errors
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc list-inside space-y-1">
              {parseErrors.map((error, index) => (
                <li key={index} className="text-sm text-destructive">{error}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6" style={{ 
        gridTemplateColumns: previewMode === 'split' ? '1fr 1fr' : '1fr'
      }}>
        {(previewMode === 'editor' || previewMode === 'split') && (
          <Card className="monaco-editor-container">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Code className="h-5 w-5" />
                YAML Editor
              </CardTitle>
              <CardDescription>
                Edit your validation rules in YAML format with syntax highlighting and real-time validation
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0">
              <Editor
                height="600px"
                language="yaml"
                theme="vs-dark"
                value={yamlContent}
                onChange={handleEditorChange}
                onMount={handleEditorMount}
                options={{
                  minimap: { enabled: true },
                  fontSize: 14,
                  lineNumbers: 'on',
                  roundedSelection: false,
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                  tabSize: 2,
                  insertSpaces: true,
                  wordWrap: 'on',
                  folding: true,
                  showFoldingControls: 'always',
                  bracketPairColorization: { enabled: true },
                  suggest: {
                    showKeywords: true,
                    showSnippets: true,
                  },
                }}
              />
            </CardContent>
          </Card>
        )}

        {(previewMode === 'preview' || previewMode === 'split') && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Eye className="h-5 w-5" />
                Rule Preview
                {ruleSet && (
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                )}
              </CardTitle>
              <CardDescription>
                Visual preview of your validation rules
              </CardDescription>
            </CardHeader>
            <CardContent className="p-0 max-h-[600px] overflow-y-auto">
              {renderPreview()}
            </CardContent>
          </Card>
        )}
      </div>

      {validationResult && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <RefreshCw className="h-5 w-5" />
              Validation Results
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold">{validationResult.total_rows}</div>
                <div className="text-sm text-muted-foreground">Total Rows</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{validationResult.processed_rows}</div>
                <div className="text-sm text-muted-foreground">Processed</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-600">{validationResult.errors?.length || 0}</div>
                <div className="text-sm text-muted-foreground">Errors</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">{validationResult.warnings?.length || 0}</div>
                <div className="text-sm text-muted-foreground">Warnings</div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}