'use client';

import React, { useState, useCallback, useRef } from 'react';
import {
  DndContext,
  DragEndEvent,
  DragStartEvent,
  DragOverlay,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { 
  RuleBuilderItem,
  RuleSet,
  ValidationRule,
  RuleField,
  RuleTemplate 
} from '@/types/rules';
import { 
  Plus, 
  Trash2, 
  Copy, 
  Settings, 
  Play, 
  Save,
  Package,
  Zap,
  Filter,
  AlertCircle,
  CheckCircle2,
  Database,
  ArrowRight,
  GripVertical 
} from 'lucide-react';
import { cn, generateId, stringifyYaml } from '@/lib/utils';

interface RuleBuilderProps {
  initialRuleSet?: RuleSet;
  onRuleSetChange?: (ruleSet: RuleSet) => void;
  onSave?: (ruleSet: RuleSet) => void;
  templates?: RuleTemplate[];
}

interface DraggableRuleItemProps {
  rule: ValidationRule;
  onEdit: (rule: ValidationRule) => void;
  onDelete: (ruleId: string) => void;
  onDuplicate: (rule: ValidationRule) => void;
}

const DraggableRuleItem: React.FC<DraggableRuleItemProps> = ({
  rule,
  onEdit,
  onDelete,
  onDuplicate,
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: rule.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'error': return 'border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950';
      case 'warning': return 'border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950';
      default: return 'border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'required': return <AlertCircle className="h-4 w-4" />;
      case 'format': return <Filter className="h-4 w-4" />;
      case 'range': return <Database className="h-4 w-4" />;
      case 'pattern': return <Zap className="h-4 w-4" />;
      default: return <Settings className="h-4 w-4" />;
    }
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={cn(
        'p-4 border-2 rounded-lg transition-all duration-200',
        getSeverityColor(rule.severity),
        isDragging && 'opacity-50 scale-95 shadow-lg',
        !rule.enabled && 'opacity-60'
      )}
    >
      <div className="flex items-start gap-3">
        <div
          {...attributes}
          {...listeners}
          className="mt-1 cursor-grab active:cursor-grabbing text-muted-foreground hover:text-foreground"
        >
          <GripVertical className="h-4 w-4" />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2">
            {getTypeIcon(rule.type)}
            <span className="font-medium text-sm">{rule.field}</span>
            <ArrowRight className="h-3 w-3 text-muted-foreground" />
            <span className="text-xs bg-white dark:bg-gray-900 px-2 py-1 rounded border">
              {rule.type}
            </span>
            <span className={cn(
              'text-xs px-2 py-1 rounded font-medium',
              rule.severity === 'error' ? 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200' :
              rule.severity === 'warning' ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200' :
              'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
            )}>
              {rule.severity}
            </span>
            {!rule.enabled && (
              <span className="text-xs bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 px-2 py-1 rounded">
                disabled
              </span>
            )}
          </div>
          
          <p className="text-sm text-muted-foreground mb-2">{rule.message}</p>
          
          <code className="text-xs bg-white dark:bg-gray-900 p-2 rounded border block">
            {rule.condition}
          </code>
        </div>

        <div className="flex gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onEdit(rule)}
            className="h-8 w-8 p-0"
          >
            <Settings className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDuplicate(rule)}
            className="h-8 w-8 p-0"
          >
            <Copy className="h-3 w-3" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onDelete(rule.id)}
            className="h-8 w-8 p-0 text-destructive hover:text-destructive"
          >
            <Trash2 className="h-3 w-3" />
          </Button>
        </div>
      </div>
    </div>
  );
};

const RuleTemplateLibrary: React.FC<{
  templates: RuleTemplate[];
  onApplyTemplate: (template: RuleTemplate) => void;
}> = ({ templates, onApplyTemplate }) => {
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  
  const categories = ['all', ...Array.from(new Set(templates.map(t => t.category)))];
  const filteredTemplates = selectedCategory === 'all' 
    ? templates 
    : templates.filter(t => t.category === selectedCategory);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Package className="h-5 w-5" />
          Template Library
        </CardTitle>
        <CardDescription>
          Choose from pre-built rule templates for common scenarios
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex gap-2 mb-4 flex-wrap">
          {categories.map(category => (
            <Button
              key={category}
              variant={selectedCategory === category ? 'default' : 'outline'}
              size="sm"
              onClick={() => setSelectedCategory(category)}
              className="text-xs"
            >
              {category.replace('_', ' ').toUpperCase()}
            </Button>
          ))}
        </div>
        
        <div className="grid gap-3 max-h-96 overflow-y-auto">
          {filteredTemplates.map(template => (
            <div
              key={template.id}
              className="p-3 border rounded-lg hover:bg-muted/50 cursor-pointer transition-colors"
              onClick={() => onApplyTemplate(template)}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h4 className="font-medium text-sm">{template.name}</h4>
                  <p className="text-xs text-muted-foreground mt-1">{template.description}</p>
                  <div className="flex items-center gap-2 mt-2">
                    <span className="text-xs bg-secondary text-secondary-foreground px-2 py-1 rounded">
                      {template.marketplace}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      v{template.version}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {template.downloads} downloads
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <div className="flex items-center gap-1 text-xs text-yellow-600">
                    {'★'.repeat(Math.floor(template.rating))}
                    <span>{template.rating}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{template.author}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

export const RuleBuilder: React.FC<RuleBuilderProps> = ({
  initialRuleSet,
  onRuleSetChange,
  onSave,
  templates = [],
}) => {
  const [ruleSet, setRuleSet] = useState<RuleSet>(
    initialRuleSet || {
      id: generateId(),
      name: 'New Rule Set',
      version: '1.0.0',
      fields: [],
      rules: [],
      metadata: {
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        created_by: 'user@validahub.com',
        tags: [],
      },
    }
  );

  const [activeId, setActiveId] = useState<string | null>(null);
  const [editingRule, setEditingRule] = useState<ValidationRule | null>(null);
  const [showTemplates, setShowTemplates] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleRuleSetUpdate = useCallback((updatedRuleSet: RuleSet) => {
    setRuleSet(updatedRuleSet);
    onRuleSetChange?.(updatedRuleSet);
  }, [onRuleSetChange]);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (active.id !== over?.id) {
      const oldIndex = ruleSet.rules.findIndex((rule) => rule.id === active.id);
      const newIndex = ruleSet.rules.findIndex((rule) => rule.id === over?.id);

      if (oldIndex !== -1 && newIndex !== -1) {
        const newRules = [...ruleSet.rules];
        const [removed] = newRules.splice(oldIndex, 1);
        newRules.splice(newIndex, 0, removed);

        const updatedRuleSet = {
          ...ruleSet,
          rules: newRules,
          metadata: {
            ...ruleSet.metadata,
            updated_at: new Date().toISOString(),
          },
        };
        handleRuleSetUpdate(updatedRuleSet);
      }
    }

    setActiveId(null);
  };

  const addNewRule = () => {
    const newRule: ValidationRule = {
      id: generateId(),
      field: 'new_field',
      type: 'required',
      condition: 'value != null',
      message: 'Field is required',
      severity: 'error',
      enabled: true,
    };

    const updatedRuleSet = {
      ...ruleSet,
      rules: [...ruleSet.rules, newRule],
      metadata: {
        ...ruleSet.metadata,
        updated_at: new Date().toISOString(),
      },
    };
    handleRuleSetUpdate(updatedRuleSet);
  };

  const deleteRule = (ruleId: string) => {
    const updatedRuleSet = {
      ...ruleSet,
      rules: ruleSet.rules.filter(rule => rule.id !== ruleId),
      metadata: {
        ...ruleSet.metadata,
        updated_at: new Date().toISOString(),
      },
    };
    handleRuleSetUpdate(updatedRuleSet);
  };

  const duplicateRule = (rule: ValidationRule) => {
    const newRule: ValidationRule = {
      ...rule,
      id: generateId(),
      field: `${rule.field}_copy`,
    };

    const updatedRuleSet = {
      ...ruleSet,
      rules: [...ruleSet.rules, newRule],
      metadata: {
        ...ruleSet.metadata,
        updated_at: new Date().toISOString(),
      },
    };
    handleRuleSetUpdate(updatedRuleSet);
  };

  const applyTemplate = (template: RuleTemplate) => {
    const updatedRuleSet = {
      ...ruleSet,
      ...template.template,
      id: ruleSet.id,
      metadata: {
        ...ruleSet.metadata,
        updated_at: new Date().toISOString(),
      },
    };
    handleRuleSetUpdate(updatedRuleSet as RuleSet);
    setShowTemplates(false);
  };

  const exportYaml = () => {
    const yaml = stringifyYaml(ruleSet);
    const blob = new Blob([yaml], { type: 'application/yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${ruleSet.name.replace(/\s+/g, '_').toLowerCase()}.yaml`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const activeRule = activeId ? ruleSet.rules.find(rule => rule.id === activeId) : null;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Rule Builder</h2>
          <p className="text-muted-foreground">
            Build validation rules visually with drag-and-drop interface
          </p>
        </div>
        
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowTemplates(!showTemplates)}>
            <Package className="h-4 w-4 mr-2" />
            Templates
          </Button>
          <Button variant="outline" onClick={exportYaml}>
            <Save className="h-4 w-4 mr-2" />
            Export YAML
          </Button>
          <Button onClick={() => onSave?.(ruleSet)}>
            <CheckCircle2 className="h-4 w-4 mr-2" />
            Save Rules
          </Button>
        </div>
      </div>

      <div className="rule-builder-grid">
        {/* Rule Set Info */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Rule Set Info</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <label className="text-sm font-medium">Name</label>
              <input
                type="text"
                value={ruleSet.name}
                onChange={(e) => handleRuleSetUpdate({
                  ...ruleSet,
                  name: e.target.value,
                  metadata: { ...ruleSet.metadata, updated_at: new Date().toISOString() }
                })}
                className="w-full mt-1 px-3 py-2 border rounded-md"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Version</label>
              <input
                type="text"
                value={ruleSet.version}
                onChange={(e) => handleRuleSetUpdate({
                  ...ruleSet,
                  version: e.target.value,
                  metadata: { ...ruleSet.metadata, updated_at: new Date().toISOString() }
                })}
                className="w-full mt-1 px-3 py-2 border rounded-md"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Description</label>
              <textarea
                value={ruleSet.description || ''}
                onChange={(e) => handleRuleSetUpdate({
                  ...ruleSet,
                  description: e.target.value,
                  metadata: { ...ruleSet.metadata, updated_at: new Date().toISOString() }
                })}
                className="w-full mt-1 px-3 py-2 border rounded-md"
                rows={3}
              />
            </div>
            
            <div className="grid grid-cols-2 gap-4 pt-4 border-t">
              <div className="text-center">
                <div className="text-2xl font-bold text-primary">{ruleSet.rules.length}</div>
                <div className="text-xs text-muted-foreground">Rules</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">
                  {ruleSet.rules.filter(r => r.enabled).length}
                </div>
                <div className="text-xs text-muted-foreground">Active</div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Rules List */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="text-lg">Validation Rules</CardTitle>
              <CardDescription>
                Drag to reorder rules. Rules are executed in order.
              </CardDescription>
            </div>
            <Button onClick={addNewRule}>
              <Plus className="h-4 w-4 mr-2" />
              Add Rule
            </Button>
          </CardHeader>
          <CardContent>
            <DndContext
              sensors={sensors}
              collisionDetection={closestCenter}
              onDragStart={handleDragStart}
              onDragEnd={handleDragEnd}
            >
              <SortableContext items={ruleSet.rules.map(rule => rule.id)} strategy={verticalListSortingStrategy}>
                <div className="space-y-3">
                  {ruleSet.rules.map((rule) => (
                    <DraggableRuleItem
                      key={rule.id}
                      rule={rule}
                      onEdit={setEditingRule}
                      onDelete={deleteRule}
                      onDuplicate={duplicateRule}
                    />
                  ))}
                  {ruleSet.rules.length === 0 && (
                    <div className="drop-zone text-center py-12">
                      <AlertCircle className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
                      <p className="text-muted-foreground">No rules defined yet</p>
                      <p className="text-sm text-muted-foreground">Click "Add Rule" to get started</p>
                    </div>
                  )}
                </div>
              </SortableContext>
              
              <DragOverlay>
                {activeRule ? (
                  <DraggableRuleItem
                    rule={activeRule}
                    onEdit={() => {}}
                    onDelete={() => {}}
                    onDuplicate={() => {}}
                  />
                ) : null}
              </DragOverlay>
            </DndContext>
          </CardContent>
        </Card>

        {/* Templates */}
        {showTemplates && (
          <RuleTemplateLibrary
            templates={templates}
            onApplyTemplate={applyTemplate}
          />
        )}
      </div>
    </div>
  );
};