#!/usr/bin/env python3
import asyncio
import json
import signal
from datetime import datetime
from enum import Enum
from typing import Set, Dict, Any
import pygame
import logging
import websockets
from pydantic import BaseModel


class GameState(Enum):
    IDLE = "idle"
    WELCOME = "welcome"
    INTERACT = "interact"
    END = "end"


class StateAction(Enum):
    ENTER = "enter"
    EXIT = "exit"
    CURRENT = "current"


class GameStateMessage(BaseModel):
    type: str = "game_state_sync"
    timestamp: int
    state: str
    action: str
    data: Dict[str, Any] = {}

    @classmethod
    def create(cls, state: GameState, action: StateAction, data: Dict[str, Any] = None):
        return cls(
            timestamp=int(datetime.now().timestamp() * 1000),
            state=state.value,
            action=action.value,
            data=data or {}
        )


logger = logging.getLogger(__name__)


class MeetaGame:
    def __init__(self, host: str = "localhost", port: int = 6666):
        self.current_state = GameState.IDLE
        self.running = True
        self.pygame_mixer = None
        self.websocket_server = None
        self.websocket_clients: Set = set()
        self.server_host = host
        self.server_port = port
        self._init_audio()
    
    def _init_audio(self):
        """Initialize audio system"""
        try:
            pygame.mixer.init()
            self.pygame_mixer = pygame.mixer
            logger.info("Audio system initialized")
        except Exception as e:
            logger.error(f"Audio init failed: {e}")
    
    async def _start_websocket_server(self):
        """Start WebSocket server"""
        try:
            self.websocket_server = await websockets.serve(
                self._handle_client,
                self.server_host,
                self.server_port
            )
            logger.info(f"WebSocket server started on {self.server_host}:{self.server_port}")
        except Exception as e:
            logger.error(f"WebSocket server start failed: {e}")
    
    async def _stop_websocket_server(self):
        """Stop WebSocket server"""
        if self.websocket_server:
            try:
                self.websocket_server.close()
                await self.websocket_server.wait_closed()
                logger.info("WebSocket server stopped")
            except Exception as e:
                logger.error(f"WebSocket server stop failed: {e}")
        
        # Close all client connections
        if self.websocket_clients:
            await asyncio.gather(
                *[client.close() for client in self.websocket_clients],
                return_exceptions=True
            )
            self.websocket_clients.clear()
    
    async def _handle_client(self, websocket):
        """Handle new client connection"""
        client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        logger.info(f"New client connected: {client_addr}")
        
        self.websocket_clients.add(websocket)
        
        try:
            # Send current game state to new client
            message = GameStateMessage.create(self.current_state, StateAction.CURRENT,
                                              {"message": "Current game state"})
            await self._send_to_client(websocket, message)
            
            # Keep connection alive and handle incoming messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    logger.debug(f"Received message from {client_addr}: {data}")
                    # Handle client messages if needed
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {client_addr}: {message}")
                    
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_addr}")
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            self.websocket_clients.discard(websocket)
    
    async def _send_to_client(self, websocket, message: GameStateMessage):
        """Send message to a specific client"""
        try:
            await websocket.send(message.model_dump_json())
            logger.debug(f"Message sent to client: {message.state}:{message.action}")
        except Exception as e:
            logger.error(f"Failed to send message to client: {e}")
    
    async def _broadcast(self, state: GameState, action: StateAction, data: Dict[str, Any] = None):
        """Broadcast state message to all connected clients"""
        if not self.websocket_clients:
            return
        
        message = GameStateMessage.create(state, action, data)
        disconnected_clients = set()
        
        for client in self.websocket_clients:
            try:
                await client.send(message.model_dump_json())
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
            except Exception as e:
                logger.error(f"Broadcast failed to client: {e}")
                disconnected_clients.add(client)
        
        self.websocket_clients -= disconnected_clients
        logger.info(f"Broadcasted {state.value}:{action.value} to {len(self.websocket_clients)} clients")
    
    async def run(self):
        """Main game loop"""
        logger.info("Game started")
        
        # Start WebSocket server
        await self._start_websocket_server()
        
        try:
            while self.running:
                if self.current_state == GameState.IDLE:
                    await self._handle_idle_state()
                elif self.current_state == GameState.WELCOME:
                    await self._handle_welcome_state()
                elif self.current_state == GameState.INTERACT:
                    await self._handle_interact_state()
                elif self.current_state == GameState.END:
                    await self._handle_end_state()
                
                if not self.running:
                    break
                    
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Game loop cancelled")
            raise
        except KeyboardInterrupt:
            logger.info("Game interrupted")
            self.stop()
        finally:
            logger.info("Game ended")
            await self._stop_websocket_server()
    
    async def _handle_idle_state(self):
        """Handle idle state - loop background music, wait for keyboard input 1"""
        logger.info("Entering IDLE state, playing background music")
        
        # Send state sync
        await self._broadcast(
            GameState.IDLE, StateAction.ENTER, {"message": "Waiting for user input"})
        
        # Play background music (loop)
        self._play_background_music()
        
        # Wait for keyboard input
        print("Press 1 to start game...")
        try:
            user_input = await self._get_keyboard_input()
            
            if user_input == "1":
                self._stop_background_music()
                await self._broadcast(
                    GameState.IDLE, StateAction.EXIT, {"user_input": "1", "next_state": "welcome"})
                self.current_state = GameState.WELCOME
                logger.info("User pressed 1, switching to WELCOME state")
        except asyncio.CancelledError:
            self._stop_background_music()
            return
    
    async def _handle_welcome_state(self):
        """Handle welcome state - play welcome audio"""
        logger.info("Entering WELCOME state, playing welcome audio")
        
        # Send state sync
        await self._broadcast(
            GameState.WELCOME, StateAction.ENTER, {"message": "Playing welcome audio", "duration": 2})
        
        # Play welcome audio
        await self._play_welcome_audio()
        
        # Auto switch to next state after audio finishes
        await self._broadcast(
            GameState.WELCOME, StateAction.EXIT, {"message": "Welcome audio finished", "next_state": "interact"})
        self.current_state = GameState.INTERACT
        logger.info("Welcome audio finished, switching to INTERACT state")
    
    async def _handle_interact_state(self):
        """Handle interact state - subprocess placeholder"""
        logger.info("Entering INTERACT state, executing interaction subprocess")
        
        # Send state sync
        await self._broadcast(
            GameState.INTERACT, StateAction.ENTER, {"message": "Starting interaction subprocess", "duration": 3})
        
        # Placeholder: simulate subprocess execution
        print("Executing interaction subprocess...")
        try:
            await asyncio.sleep(3)  # Simulate subprocess execution time
        except asyncio.CancelledError:
            logger.info("Interaction subprocess cancelled")
            raise
        
        # Subprocess finished, switch to end state
        await self._broadcast(
            GameState.INTERACT, StateAction.EXIT, {"message": "Interaction subprocess finished", "next_state": "end"})
        self.current_state = GameState.END
        logger.info("Interaction subprocess finished, switching to END state")
    
    async def _handle_end_state(self):
        """Handle end state - play end audio"""
        logger.info("Entering END state, playing end audio")
        
        # Send state sync
        await self._broadcast(
            GameState.END, StateAction.ENTER, {"message": "Playing end audio", "duration": 2})
        
        # Play end audio
        await self._play_end_audio()
        
        # Return to idle state, start new cycle
        await self._broadcast(
            GameState.END, StateAction.EXIT, {"message": "End audio finished, returning to idle", "next_state": "idle"})
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
        except asyncio.CancelledError:
            logger.info("Welcome audio cancelled")
            raise
        except Exception as e:
            logger.error(f"Playing welcome audio failed: {e}")
    
    async def _play_end_audio(self):
        """Play end audio"""
        try:
            print("🎤 Playing end audio")
            # Simulate audio playback time
            await asyncio.sleep(2)
            print("🎤 End audio finished")
        except asyncio.CancelledError:
            logger.info("End audio cancelled")
            raise
        except Exception as e:
            logger.error(f"Playing end audio failed: {e}")
    
    async def _get_keyboard_input(self) -> str:
        """Async keyboard input with cancellation support"""
        import sys
        import select
        
        while self.running:
            try:
                # 检查是否被中断
                if not self.running:
                    break
                    
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    line = sys.stdin.readline().strip()
                    return line
                await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                return ""
            except Exception:
                return ""
        return ""
    
    def stop(self):
        """Stop game"""
        self.running = False
        self._stop_background_music()
        logger.info("Game stopping...")
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        loop = asyncio.get_event_loop()
        
        def signal_handler():
            logger.info("Received interrupt signal, stopping game...")
            self.stop()
            # 取消所有正在运行的任务
            for task in asyncio.all_tasks(loop):
                if not task.done():
                    task.cancel()
        
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)

async def main():
    """Main function"""
    logging.basicConfig(level=logging.INFO)
    
    game = MeetaGame()
    
    task = None
    try:
        game._setup_signal_handlers()
        task = asyncio.create_task(game.run())
        await task
    except KeyboardInterrupt:
        logger.info("Game interrupted by user")
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                logger.info("Game task cancelled gracefully")
    except asyncio.CancelledError:
        logger.info("Game cancelled gracefully")
    except Exception as e:
        logger.error(f"Game runtime exception: {e}")
    finally:
        game.stop()
        if game.pygame_mixer:
            pygame.mixer.quit()
        logger.info("Game shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())