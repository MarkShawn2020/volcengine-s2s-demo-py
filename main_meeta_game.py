#!/usr/bin/env python3
import asyncio
import sys
import threading
from enum import Enum
from typing import Optional
import pygame
import logging

logger = logging.getLogger(__name__)

class GameState(Enum):
    IDLE = "idle"
    WELCOME = "welcome"
    INTERACT = "interact"
    END = "end"

class MeetaGame:
    def __init__(self):
        self.current_state = GameState.IDLE
        self.running = True
        self.pygame_mixer = None
        self._init_audio()
    
    def _init_audio(self):
        """Initialize audio system"""
        try:
            pygame.mixer.init()
            self.pygame_mixer = pygame.mixer
            logger.info("Audio system initialized successfully")
        except Exception as e:
            logger.error(f"Audio system initialization failed: {e}")
    
    async def run(self):
        """Main game loop"""
        logger.info("Game started")
        
        while self.running:
            if self.current_state == GameState.IDLE:
                await self._handle_idle_state()
            elif self.current_state == GameState.WELCOME:
                await self._handle_welcome_state()
            elif self.current_state == GameState.INTERACT:
                await self._handle_interact_state()
            elif self.current_state == GameState.END:
                await self._handle_end_state()
            
            await asyncio.sleep(0.1)
        
        logger.info("Game ended")
    
    async def _handle_idle_state(self):
        """Handle idle state - loop background music, wait for keyboard input 1"""
        logger.info("Entering IDLE state, playing background music")
        
        # Play background music (loop)
        self._play_background_music()
        
        # Wait for keyboard input
        print("Press 1 to start game...")
        user_input = await self._get_keyboard_input()
        
        if user_input == "1":
            self._stop_background_music()
            self.current_state = GameState.WELCOME
            logger.info("User pressed 1, switching to WELCOME state")
    
    async def _handle_welcome_state(self):
        """Handle welcome state - play welcome audio"""
        logger.info("Entering WELCOME state, playing welcome audio")
        
        # Play welcome audio
        await self._play_welcome_audio()
        
        # Auto switch to next state after audio finishes
        self.current_state = GameState.INTERACT
        logger.info("Welcome audio finished, switching to INTERACT state")
    
    async def _handle_interact_state(self):
        """Handle interact state - subprocess placeholder"""
        logger.info("Entering INTERACT state, executing interaction subprocess")
        
        # Placeholder: simulate subprocess execution
        print("Executing interaction subprocess...")
        await asyncio.sleep(3)  # Simulate subprocess execution time
        
        # Subprocess finished, switch to end state
        self.current_state = GameState.END
        logger.info("Interaction subprocess finished, switching to END state")
    
    async def _handle_end_state(self):
        """Handle end state - play end audio"""
        logger.info("Entering END state, playing end audio")
        
        # Play end audio
        await self._play_end_audio()
        
        # Return to idle state, start new cycle
        self.current_state = GameState.IDLE
        logger.info("End audio finished, returning to IDLE state")
    
    def _play_background_music(self):
        """Play background music"""
        try:
            if self.pygame_mixer:
                # Assuming music file exists, actual use requires audio file path
                # self.pygame_mixer.music.load("background_music.mp3")
                # self.pygame_mixer.music.play(-1)  # -1 means infinite loop
                print("🎵 Playing background music (loop)")
        except Exception as e:
            logger.error(f"Playing background music failed: {e}")
    
    def _stop_background_music(self):
        """Stop background music"""
        try:
            if self.pygame_mixer:
                self.pygame_mixer.music.stop()
                print("🎵 Stopped background music")
        except Exception as e:
            logger.error(f"Stopping background music failed: {e}")
    
    async def _play_welcome_audio(self):
        """Play welcome audio"""
        try:
            print("🎤 Playing welcome audio")
            # Simulate audio playback time
            await asyncio.sleep(2)
            print("🎤 Welcome audio finished")
        except Exception as e:
            logger.error(f"Playing welcome audio failed: {e}")
    
    async def _play_end_audio(self):
        """Play end audio"""
        try:
            print("🎤 Playing end audio")
            # Simulate audio playback time
            await asyncio.sleep(2)
            print("🎤 End audio finished")
        except Exception as e:
            logger.error(f"Playing end audio failed: {e}")
    
    async def _get_keyboard_input(self) -> str:
        """Async keyboard input"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, input)
    
    def stop(self):
        """Stop game"""
        self.running = False
        self._stop_background_music()

async def main():
    """Main function"""
    logging.basicConfig(level=logging.INFO)
    
    game = MeetaGame()
    
    try:
        await game.run()
    except KeyboardInterrupt:
        print("\nGame interrupted by user")
        game.stop()
    except Exception as e:
        logger.error(f"Game runtime exception: {e}")
        game.stop()
    finally:
        if game.pygame_mixer:
            pygame.mixer.quit()

if __name__ == "__main__":
    asyncio.run(main())