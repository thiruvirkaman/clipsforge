import { motion } from 'framer-motion';
import { InputHTMLAttributes, forwardRef, useId } from 'react';
import { cn } from '@/lib/utils';

// Omit native DOM event handlers whose signatures clash with framer-motion's
// (e.g. onAnimationStart/onDrag*) since motion.input re-types them.
type NativeInputProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  | 'onAnimationStart'
  | 'onAnimationEnd'
  | 'onAnimationIteration'
  | 'onDrag'
  | 'onDragEnd'
  | 'onDragStart'
>;

interface AnimatedInputProps extends NativeInputProps {
  label?: string;
  error?: string;
}

export const AnimatedInput = forwardRef<HTMLInputElement, AnimatedInputProps>(
  ({ label, error, className, id, ...props }, ref) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;
    return (
      <div>
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium mb-1">
            {label}
          </label>
        )}
        <motion.input
          ref={ref}
          id={inputId}
          whileFocus={{ scale: 1.01 }}
          className={cn(
            'w-full px-4 py-3 rounded-xl border-2 outline-none transition-colors',
            error
              ? 'border-red-500'
              : 'border-gray-200 focus:border-purple-500',
            className
          )}
          {...props}
        />
        {error && <p className="text-red-500 text-sm mt-1">{error}</p>}
      </div>
    );
  }
);

AnimatedInput.displayName = 'AnimatedInput';
