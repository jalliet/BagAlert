import React, { useState, useEffect, useRef } from 'react';
import {
	AppBar,
	Toolbar,
	Typography,
	Container,
	Box,
	Button,
	IconButton,
	Fab,
	Chip,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import CheckIcon from '@mui/icons-material/Check';
import WarningIcon from '@mui/icons-material/Warning';

// WebSocket Camera Component (previously separate)
interface CameraFeedProps {
  activated: boolean;
}

const CameraFeed: React.FC<CameraFeedProps> = ({ activated }) => {
  const [imageUrl, setImageUrl] = useState<string>('');
  const [connected, setConnected] = useState<boolean>(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);

  // Get appropriate WebSocket URL based on current hostname
  const getWebSocketUrl = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.hostname === 'localhost' ? 
      'localhost:5000' : 
      `${window.location.hostname}:5000`;
    return `${protocol}//${host}/live`;
  };

  // Connect to WebSocket
  const connectWebSocket = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return; // Already connected
    }

    // Clear any existing reconnect timer
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    try {
      const ws = new WebSocket(getWebSocketUrl());
      
      ws.onopen = () => {
        console.log('WebSocket connected');
        setConnected(true);
      };
      
      ws.onmessage = (event) => {
        // Set image source from base64 data
        setImageUrl(`data:image/jpeg;base64,${event.data}`);
      };
      
      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setConnected(false);
        
        // Try to reconnect after a delay
        reconnectTimerRef.current = window.setTimeout(() => {
          console.log('Attempting to reconnect...');
          connectWebSocket();
        }, 2000);
      };
      
      ws.onerror = (err) => {
        console.error('WebSocket error:', err);
        setConnected(false);
      };
      
      wsRef.current = ws;
    } catch (err) {
      console.error('Error creating WebSocket:', err);
      
      // Try to reconnect after a delay
      reconnectTimerRef.current = window.setTimeout(() => {
        connectWebSocket();
      }, 3000);
    }
  };

  // Connect when component mounts
  useEffect(() => {
    connectWebSocket();
    
    // Cleanup when component unmounts
    return () => {
      if (reconnectTimerRef.current !== null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Change frame rate based on activated state
  useEffect(() => {
    if (connected) {
      // Lower frame rate when not activated to save resources
      const frameRate = activated ? 30 : 10;
      fetch(`/set_frame_rate/${frameRate}`)
        .catch(err => console.error('Error updating frame rate:', err));
    }
  }, [activated, connected]);

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#222',
        position: 'relative',
      }}
    >
      {imageUrl && (
        <img
          src={imageUrl}
          alt="Camera Feed"
          style={{
            maxWidth: '1000px',
            maxHeight: '1000px',
            objectFit: 'contain',
          }}
        />
      )}
      {/* Connection status indicator */}
      <Box
        sx={{
          position: 'absolute',
          top: '10px',
          right: '10px',
          backgroundColor: connected ? 'rgba(0,255,0,0.3)' : 'rgba(255,0,0,0.3)',
          color: 'white',
          padding: '4px 8px',
          borderRadius: '4px',
          fontSize: '12px',
        }}
      >
        {connected ? 'Connected' : 'Disconnected'}
      </Box>
    </Box>
  );
};

const App: React.FC = () => {
	// State for the activated flag and selected screen
	const [activated, setActivated] = useState<boolean>(false);
	const [selectedScreen, setSelectedScreen] = useState('live'); // Default to live screen

	// Function triggered by the red exclamation mark Fab
	const callLEDs = () => {
		// Call LEDs
	};

	return (
		<div className='App'>
			<Container
				maxWidth='xl'
				style={{
					backgroundColor: '#000',
					color: '#fff',
					minHeight: '100vh',
					padding: 0,
					position: 'relative',
					display: 'flex',
					flexDirection: 'column',
				}}>
				{/* Header */}
				<AppBar position='static' style={{ backgroundColor: 'inherit' }}>
					<Toolbar variant='dense'>
						<IconButton edge='start' color='inherit' style={{ marginRight: '8px' }}>
							<MenuIcon />
						</IconButton>
						<Chip
							label='Live'
							size='small'
							style={{
								backgroundColor: '#333',
								color: activated ? 'red' : 'green',
								fontWeight: 'bold',
								marginRight: '8px',
							}}
						/>
						<Typography variant='body2'>80%</Typography>
					</Toolbar>
				</AppBar>

				{/* Main Content Area */}
				<Box
					style={{
						flex: 1,
						padding: '16px 32px', // Reduced horizontal padding to use more screen width
						overflow: 'auto',
						display: 'flex',
						flexDirection: 'column',
					}}>
					{selectedScreen === 'history' && (
						<Typography variant='body2'>History Content</Typography>
					)}
					{selectedScreen === 'live' && (
						<Box
							style={{
								flex: 1,
								position: 'relative',
								width: '100%',
								marginTop: '8px',
								marginBottom: '170px',
								height: 'calc(100vh - 300px)', // Increased height
							}}>
							<CameraFeed activated={activated} />
						</Box>
					)}
					{selectedScreen === 'sessions' && (
						<Typography variant='body2'>Sessions Content</Typography>
					)}
				</Box>

				{/* Bottom Controls Container */}
				<Box
					style={{
						position: 'fixed',
						bottom: 0,
						left: 0,
						width: '100%',
						display: 'flex',
						flexDirection: 'column',
						alignItems: 'center',
						gap: '8px',
						padding: '8px',
						backgroundColor: 'rgba(0,0,0,0.7)',
					}}>
					{/* FAB Buttons */}
					<Box
						style={{
							display: 'flex',
							justifyContent: 'center',
							gap: '16px',
							marginBottom: '15px',
						}}>
						<Fab
							onClick={callLEDs}
							style={{ backgroundColor: 'red', color: '#fff' }}
							aria-label='alert'>
							<WarningIcon />
						</Fab>
						<Fab
							onClick={() => setActivated(prev => !prev)}
							style={{ 
                backgroundColor: activated ? 'green' : 'blue', 
                color: '#fff' 
              }}
							aria-label='confirm'>
							<CheckIcon />
						</Fab>
					</Box>

					{/* Screen Selection Buttons */}
					<Box
						style={{
							display: 'flex',
							justifyContent: 'center',
							gap: '18px',
							paddingBottom: '18px',
						}}>
						<Button
							onClick={() => setSelectedScreen('history')}
							style={{
								backgroundColor: selectedScreen === 'history' ? '#fff' : 'transparent',
								color: selectedScreen === 'history' ? '#000' : '#fff',
								flex: 1,
							}}>
							History
						</Button>
						<Button
							onClick={() => setSelectedScreen('live')}
							style={{
								backgroundColor: selectedScreen === 'live' ? '#fff' : 'transparent',
								color: selectedScreen === 'live' ? '#000' : '#fff',
								flex: 1,
							}}>
							Live
						</Button>
						<Button
							onClick={() => setSelectedScreen('sessions')}
							style={{
								backgroundColor: selectedScreen === 'sessions' ? '#fff' : 'transparent',
								color: selectedScreen === 'sessions' ? '#000' : '#fff',
								flex: 1,
							}}>
							Sessions
						</Button>
					</Box>
				</Box>
			</Container>
		</div>
	);
};

export default App;