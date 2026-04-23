import React from 'react';
import { motion } from 'motion/react';

export default function ShopeeLoading() {
  return (
    <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center bg-white">
      <div className="relative flex h-48 w-48 items-center justify-center">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{
            duration: 0.8,
            repeat: Infinity,
            ease: 'linear',
          }}
          className="absolute inset-0 rounded-full border-[8px] border-[#ee4d2d] border-r-transparent border-t-transparent"
        />

        <div className="relative">
          <motion.span
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.3 }}
            className="font-sans text-7xl font-bold text-[#ee4d2d]"
            style={{ lineHeight: 1 }}
          >
            S
          </motion.span>
        </div>
      </div>
    </div>
  );
}
