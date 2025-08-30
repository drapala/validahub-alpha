import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Code2,
  BarChart3,
  Puzzle,
  Zap,
  Shield,
  Clock,
  ArrowRight,
  Github,
  ExternalLink,
} from 'lucide-react';

export default function HomePage() {
  const features = [
    {
      icon: <Code2 className="h-8 w-8" />,
      title: 'Monaco Editor',
      description: 'Professional YAML editing with syntax highlighting, autocomplete, and real-time validation',
      href: '/rules/editor',
    },
    {
      icon: <Puzzle className="h-8 w-8" />,
      title: 'Visual Rule Builder',
      description: 'Drag-and-drop interface for building complex validation rules without writing code',
      href: '/rules/builder',
    },
    {
      icon: <BarChart3 className="h-8 w-8" />,
      title: 'Real-time Analytics',
      description: 'Live dashboards with SSE-powered metrics, performance insights, and validation trends',
      href: '/rules/analytics',
    },
    {
      icon: <Zap className="h-8 w-8" />,
      title: 'Smart Suggestions',
      description: 'AI-powered rule optimization recommendations and automatic error detection',
      href: '/rules/suggestions',
    },
    {
      icon: <Shield className="h-8 w-8" />,
      title: 'Version Control',
      description: 'Complete rule versioning with rollback capabilities and change history tracking',
      href: '/rules/versions',
    },
    {
      icon: <Clock className="h-8 w-8" />,
      title: 'Instant Validation',
      description: 'Server-sent events for real-time validation feedback and processing updates',
      href: '/rules/validation',
    },
  ];

  return (
    <div className="container mx-auto py-12 space-y-16">
      {/* Hero Section */}
      <div className="text-center space-y-6">
        <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary rounded-full text-sm font-medium">
          <Zap className="h-4 w-4" />
          Smart Rules Engine
        </div>
        <h1 className="text-4xl md:text-6xl font-bold tracking-tight">
          Build Validation Rules
          <span className="block text-primary">Visually & Intuitively</span>
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Create, test, and deploy CSV validation rules with our advanced rule engine. 
          Features Monaco editor, drag-and-drop builder, and real-time analytics.
        </p>
        <div className="flex gap-4 justify-center">
          <Button size="lg" asChild>
            <Link href="/rules/editor">
              Get Started
              <ArrowRight className="h-4 w-4 ml-2" />
            </Link>
          </Button>
          <Button size="lg" variant="outline" asChild>
            <Link href="/rules/analytics">
              View Analytics
              <BarChart3 className="h-4 w-4 ml-2" />
            </Link>
          </Button>
        </div>
      </div>

      {/* Features Grid */}
      <div className="space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">Powerful Features</h2>
          <p className="text-muted-foreground">
            Everything you need to build, test, and manage validation rules at scale
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature, index) => (
            <Card key={index} className="group cursor-pointer hover:shadow-lg transition-all duration-200">
              <Link href={feature.href}>
                <CardHeader>
                  <div className="flex items-center gap-4">
                    <div className="p-2 bg-primary/10 text-primary rounded-lg group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                      {feature.icon}
                    </div>
                    <CardTitle className="text-xl">{feature.title}</CardTitle>
                  </div>
                </CardHeader>
                <CardContent>
                  <CardDescription className="text-base">
                    {feature.description}
                  </CardDescription>
                  <div className="mt-4 flex items-center text-primary text-sm font-medium group-hover:text-primary/80">
                    Learn more
                    <ArrowRight className="h-3 w-3 ml-1 group-hover:translate-x-1 transition-transform" />
                  </div>
                </CardContent>
              </Link>
            </Card>
          ))}
        </div>
      </div>

      {/* Technology Stack */}
      <div className="space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-3xl font-bold tracking-tight">Built with Modern Tech</h2>
          <p className="text-muted-foreground">
            Leveraging the latest web technologies for optimal performance and developer experience
          </p>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { name: 'Next.js 15', description: 'React framework with App Router' },
            { name: 'Monaco Editor', description: 'VS Code-powered editor' },
            { name: 'shadcn/ui', description: 'Modern component library' },
            { name: 'Server-Sent Events', description: 'Real-time data streaming' },
            { name: 'Chart.js', description: 'Interactive analytics charts' },
            { name: 'DND Kit', description: 'Drag-and-drop functionality' },
            { name: 'TypeScript', description: 'Type-safe development' },
            { name: 'Playwright', description: 'End-to-end testing' },
          ].map((tech, index) => (
            <Card key={index}>
              <CardContent className="p-4 text-center">
                <h3 className="font-semibold">{tech.name}</h3>
                <p className="text-sm text-muted-foreground mt-1">{tech.description}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Quick Start */}
      <Card className="bg-gradient-to-r from-primary/10 via-primary/5 to-transparent border-primary/20">
        <CardContent className="p-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="space-y-2">
              <h2 className="text-2xl font-bold">Ready to start building rules?</h2>
              <p className="text-muted-foreground">
                Jump into our Monaco editor and create your first validation rule set
              </p>
            </div>
            <div className="flex gap-3">
              <Button size="lg" asChild>
                <Link href="/rules/editor">
                  Open Editor
                  <Code2 className="h-4 w-4 ml-2" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="https://github.com/validahub/smart-rules-engine" target="_blank">
                  <Github className="h-4 w-4 mr-2" />
                  GitHub
                  <ExternalLink className="h-3 w-3 ml-1" />
                </Link>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Footer */}
      <div className="text-center text-sm text-muted-foreground">
        <p>
          Built with ❤️ using Next.js 15, shadcn/ui, and modern web technologies
        </p>
      </div>
    </div>
  );
}