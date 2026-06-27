import React from 'react';

export const PlanSkeleton: React.FC = () => {
  return (
    <div className="space-y-6 animate-pulse" data-testid="plan-skeleton">
      {/* Meta header skeleton */}
      <div className="h-4 bg-card rounded w-1/4 mb-4" />
      <div className="h-3 bg-card rounded w-1/3 mb-8" />

      {/* Phase Skeletons */}
      {[1, 2, 3].map((i) => (
        <div key={i} className="p-4 bg-card/50 border border-border rounded-lg space-y-4">
          <div className="h-5 bg-secondary rounded w-1/3" />
          <div className="space-y-2">
            <div className="h-3 bg-secondary rounded w-full" />
            <div className="h-3 bg-secondary rounded w-5/6" />
          </div>
          {/* Milestones grid mock */}
          <div className="grid grid-cols-4 gap-2 pt-2">
            <div className="h-8 bg-secondary rounded col-span-1" />
            <div className="h-8 bg-secondary rounded col-span-2" />
            <div className="h-8 bg-secondary rounded col-span-1" />
          </div>
        </div>
      ))}
    </div>
  );
};
