import { motion } from 'framer-motion';
import { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

// Omit native DOM event handlers whose signatures clash with framer-motion's
// (e.g. onAnimationStart/onDrag*) since motion.button re-types them.
type GradientButtonProps = Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  | 'onAnimationStart'
  | 'onAnimationEnd'
  | 'onAnimationIteration'
  | 'onDrag'
  | 'onDragEnd'
  | 'onDragStart'
>;

export function GradientButton({
  children,
  className,
  ...props
}: GradientButtonProps) {
  return (
    <motion.button
      whileHover={{ scale: 1.02, y: -2 }}
      whileTap={{ scale: 0.98 }}
      className={cn(
        'px-6 py-3 rounded-full font-semibold text-white bg-gradient-to-r from-purple-500 to-pink-500 hover:shadow-lg disabled:opacity-50 disabled:pointer-events-none',
        className
      )}
      {...props}
    >
      {children}
    </motion.button>
  );
}
