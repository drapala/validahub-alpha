'use client';

import { RuleBuilder } from '@/components/RuleBuilder';
import { RuleSet, RuleTemplate } from '@/types/rules';
import { useState } from 'react';

// Mock templates for demonstration
const mockTemplates: RuleTemplate[] = [
  {
    id: 'ecommerce-basic',
    name: 'E-commerce Basic',
    description: 'Essential product validation rules for online stores',
    category: 'ecommerce',
    marketplace: 'mercado_livre',
    version: '1.0.0',
    downloads: 1250,
    rating: 4.8,
    author: 'ValidaHub Team',
    template: {
      name: 'E-commerce Product Validation',
      description: 'Basic validation rules for product listings',
      fields: [
        { name: 'title', type: 'string', required: true, description: 'Product title' },
        { name: 'price', type: 'number', required: true, description: 'Product price' },
        { name: 'category', type: 'string', required: true, description: 'Product category' },
        { name: 'description', type: 'string', required: false, description: 'Product description' },
      ],
      rules: [
        {
          id: 'title_required',
          field: 'title',
          type: 'required',
          condition: 'value != null && value.trim().length > 0',
          message: 'Product title is required',
          severity: 'error',
          enabled: true,
        },
        {
          id: 'title_length',
          field: 'title',
          type: 'range',
          condition: 'value.length >= 10 && value.length <= 200',
          message: 'Product title must be between 10 and 200 characters',
          severity: 'warning',
          enabled: true,
        },
        {
          id: 'price_positive',
          field: 'price',
          type: 'range',
          condition: 'value > 0',
          message: 'Product price must be positive',
          severity: 'error',
          enabled: true,
        },
      ],
    },
  },
  {
    id: 'financial-data',
    name: 'Financial Data Validation',
    description: 'Comprehensive validation for financial datasets',
    category: 'finance',
    marketplace: 'generic',
    version: '2.1.0',
    downloads: 890,
    rating: 4.6,
    author: 'FinanceTeam',
    template: {
      name: 'Financial Data Rules',
      description: 'Validation rules for financial data integrity',
      fields: [
        { name: 'amount', type: 'number', required: true, description: 'Transaction amount' },
        { name: 'currency', type: 'string', required: true, description: 'Currency code' },
        { name: 'date', type: 'date', required: true, description: 'Transaction date' },
        { name: 'account_id', type: 'string', required: true, description: 'Account identifier' },
      ],
      rules: [
        {
          id: 'amount_precision',
          field: 'amount',
          type: 'format',
          condition: 'Math.round(value * 100) / 100 === value',
          message: 'Amount must have at most 2 decimal places',
          severity: 'error',
          enabled: true,
        },
        {
          id: 'currency_code',
          field: 'currency',
          type: 'pattern',
          condition: '^[A-Z]{3}$',
          message: 'Currency must be a valid 3-letter ISO code',
          severity: 'error',
          enabled: true,
        },
      ],
    },
  },
  {
    id: 'user-data',
    name: 'User Data Compliance',
    description: 'LGPD/GDPR compliant user data validation',
    category: 'compliance',
    marketplace: 'generic',
    version: '1.5.0',
    downloads: 2100,
    rating: 4.9,
    author: 'ComplianceTeam',
    template: {
      name: 'User Data Validation',
      description: 'Privacy-compliant user data validation rules',
      fields: [
        { name: 'email', type: 'email', required: true, description: 'User email address' },
        { name: 'phone', type: 'string', required: false, description: 'Phone number' },
        { name: 'birth_date', type: 'date', required: false, description: 'Date of birth' },
        { name: 'document_id', type: 'string', required: false, description: 'Identity document' },
      ],
      rules: [
        {
          id: 'email_format',
          field: 'email',
          type: 'format',
          condition: 'email_regex_pattern',
          message: 'Invalid email format',
          severity: 'error',
          enabled: true,
        },
        {
          id: 'phone_format',
          field: 'phone',
          type: 'pattern',
          condition: '^\\+?[1-9]\\d{1,14}$',
          message: 'Phone number must be in international format',
          severity: 'warning',
          enabled: true,
        },
        {
          id: 'age_verification',
          field: 'birth_date',
          type: 'custom',
          condition: 'age >= 13',
          message: 'User must be at least 13 years old',
          severity: 'error',
          enabled: true,
        },
      ],
    },
  },
];

export default function RuleBuilderPage() {
  const [currentRuleSet, setCurrentRuleSet] = useState<RuleSet | undefined>(undefined);

  const handleRuleSetChange = (ruleSet: RuleSet) => {
    setCurrentRuleSet(ruleSet);
    console.log('Rule set updated:', ruleSet);
  };

  const handleSave = async (ruleSet: RuleSet) => {
    try {
      const response = await fetch('/api/rules', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(ruleSet),
      });

      if (response.ok) {
        console.log('Rule set saved successfully');
        // In a real app, you'd show a success toast notification
      } else {
        console.error('Failed to save rule set');
        // In a real app, you'd show an error toast notification
      }
    } catch (error) {
      console.error('Error saving rule set:', error);
    }
  };

  return (
    <div className="container mx-auto py-6">
      <RuleBuilder
        initialRuleSet={currentRuleSet}
        onRuleSetChange={handleRuleSetChange}
        onSave={handleSave}
        templates={mockTemplates}
      />
    </div>
  );
}