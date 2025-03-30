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
	Alert,
	List,
	ListItem,
	ListItemText,
	Paper,
	Divider,
	Badge,
} from '@mui/material';
import MenuIcon from '@mui/icons-material/Menu';
import CheckIcon from '@mui/icons-material/Check';
import WarningIcon from '@mui/icons-material/Warning';
import NotificationsIcon from '@mui/icons-material/Notifications';
import { enqueueSnackbar, useSnackbar } from 'notistack';

// WebSocket Camera Component with Protection Features
interface CameraFeedProps {
	activated: boolean;
}

interface Disturbance {
	item: string;
	movement_score: number;
	missing?: boolean;
	original_bbox: number[];
	current_bbox?: number[] | null;
	current_image?: string;
}

interface AlertData {
	timestamp: number;
	disturbances: Disturbance[];
}

const CameraFeed: React.FC<CameraFeedProps> = ({ activated }) => {
	const [imageUrl, setImageUrl] = useState<string>('');
	const [connected, setConnected] = useState<boolean>(false);
	const [alerts, setAlerts] = useState<AlertData[]>([]);
	const [protectionStatus, setProtectionStatus] = useState<string>('Not active');
	const wsRef = useRef<WebSocket | null>(null);
	const reconnectTimerRef = useRef<number | null>(null);

	// Get appropriate WebSocket URL based on current hostname
	const getWebSocketUrl = () => {
		const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
		const host =
			window.location.hostname === 'localhost'
				? 'localhost:5000'
				: `${window.location.hostname}:5000`;
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

			ws.onmessage = event => {
				try {
					// Try to parse as JSON first (could be an alert)
					const jsonMsg = JSON.parse(event.data);
					if (jsonMsg.type === 'alert') {
						console.log('Received alert:', jsonMsg.data);
						// Add alert to state
						setAlerts(prev => [jsonMsg.data, ...prev].slice(0, 10)); // Keep only last 10 alerts
					}
				} catch (e) {
					// Not JSON, so it's a frame
					setImageUrl(`data:image/jpeg;base64,${event.data}`);
				}
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

			ws.onerror = err => {
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

	const MyButton = () => {
		const { enqueueSnackbar, closeSnackbar } = useSnackbar();
		return <Button onClick={() => enqueueSnackbar('I love hooks')}>Show snackbar</Button>;
	};

	// Handle activation/deactivation
	useEffect(() => {
		if (connected) {
			// When activated, initiate object protection
			if (activated) {
				fetch('/activate_protection')
					.then(response => response.json())
					.then(data => {
						if (data.success) {
							setProtectionStatus(
								`Protection active: monitoring ${data.object_count} objects`
							);
							// Reset alerts when protection is newly activated
							setAlerts([]);
						} else {
							setProtectionStatus(`Failed to activate protection: ${data.message}`);
						}
					})
					.catch(err => {
						console.error('Error activating protection:', err);
						setProtectionStatus('Error activating protection');
					});
			} else {
				// When deactivated, stop protection
				fetch('/deactivate_protection')
					.then(() => {
						setProtectionStatus('Protection not active');
					})
					.catch(err => {
						console.error('Error deactivating protection:', err);
					});
			}

			// Change frame rate based on activated state
			const frameRate = activated ? 30 : 10;
			fetch(`/set_frame_rate/${frameRate}`).catch(err =>
				console.error('Error updating frame rate:', err)
			);
		}
	}, [activated, connected]);

	return (
		<Box
			sx={{
				width: '100%',
				height: '100%',
				display: 'flex',
				flexDirection: 'column',
				backgroundColor: '#222',
				position: 'relative',
			}}>
			{/* Status display */}
			<Box
				sx={{
					position: 'absolute',
					top: '10px',
					left: '10px',
					zIndex: 10,
					backgroundColor: 'rgba(0,0,0,0.5)',
					padding: '8px',
					borderRadius: '4px',
				}}>
				<Typography color={connected ? 'success.main' : 'error.main'} variant='body2'>
					{connected ? 'Connected' : 'Disconnected'}
				</Typography>
				<Typography color={activated ? 'success.main' : 'text.secondary'} variant='body2'>
					{protectionStatus}
				</Typography>
			</Box>

			{/* Camera feed */}
			<Box
				sx={{
					flex: 1,
					display: 'flex',
					justifyContent: 'center',
					alignItems: 'center',
					overflow: 'hidden',
					position: 'relative',
				}}>
				{imageUrl ? (
					<img
						src={imageUrl}
						alt='Camera Feed'
						style={{
							maxWidth: '100%',
							maxHeight: '100%',
							objectFit: 'contain',
						}}
					/>
				) : (
					<Typography color='gray'>No video feed available</Typography>
				)}

				{/* Protection overlay - only shown when activated */}
				{activated && (
					<Box
						sx={{
							position: 'absolute',
							top: '20%',
							left: '20%',
							width: '60%',
							height: '60%',
							border: '2px solid red',
							pointerEvents: 'none',
							boxShadow: '0 0 10px rgba(255,0,0,0.5)',
							zIndex: 5,
						}}
					/>
				)}
			</Box>

			{/* Alerts section */}
			{activated && alerts.length > 0 && (
				<Paper
					elevation={3}
					sx={{
						maxHeight: '20vh',
						overflowY: 'auto',
						backgroundColor: 'rgba(30,30,30,0.9)',
						m: 1,
						color: 'white',
					}}>
					<List dense>
						<ListItem>
							<ListItemText
								primary={
									<Typography variant='h6' color='error'>
										Recent Alerts
									</Typography>
								}
							/>
						</ListItem>
						<Divider sx={{ backgroundColor: 'rgba(255,255,255,0.1)' }} />
						{alerts.map((alert, alertIndex) => (
							<React.Fragment key={alertIndex}>
								{alert.disturbances.map((disturbance, distIndex) => (
									<ListItem
										key={`${alertIndex}-${distIndex}`}
										sx={{ color: 'error.main' }}>
										<ListItemText
											primary={
												<Typography variant='body2'>
													{disturbance.missing
														? `${disturbance.item} is MISSING!`
														: `${disturbance.item} has moved (${Math.round(
																disturbance.movement_score * 100
														  )}% change)`}
												</Typography>
											}
											secondary={
												<Typography variant='caption' color='text.secondary'>
													{new Date(alert.timestamp * 1000).toLocaleTimeString()}
												</Typography>
											}
										/>
									</ListItem>
								))}
							</React.Fragment>
						))}
					</List>
				</Paper>
			)}
		</Box>
	);
};

const App: React.FC = () => {
	// State for the activated flag and selected screen
	const [activated, setActivated] = useState<boolean>(false);
	const [selectedScreen, setSelectedScreen] = useState('live'); // Default to live screen
	const [alertCount, setAlertCount] = useState<number>(0);

	// Function triggered by the red exclamation mark Fab
	const callLEDs = () => {
		// This would connect to hardware LEDs
		// For testing, simulate an RFID trigger
		fetch('/simulate_rfid_trigger')
			.then(response => response.json())
			.then(data => {
				console.log('RFID trigger simulated:', data);
				// Automatically activate protection when RFID is triggered
				if (!activated) {
					setActivated(true);
				}
			})
			.catch(err => console.error('Error simulating RFID trigger:', err));
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
							label={activated ? 'Protected' : 'Live'}
							size='small'
							style={{
								backgroundColor: '#333',
								color: activated ? 'red' : 'green',
								fontWeight: 'bold',
								marginRight: '8px',
							}}
						/>
						<Typography variant='body2' style={{ flexGrow: 1 }}>
							BagAlert
						</Typography>

						{/* Notifications */}
						<Badge
							badgeContent={alertCount}
							onClick={() => enqueueSnackbar({ message: 'Object removal detected' })}
							color='error'
							sx={{ mr: 2 }}>
							<NotificationsIcon />
						</Badge>
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
								height: 'calc(100vh - 200px)', // Increased height
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
								color: '#fff',
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
