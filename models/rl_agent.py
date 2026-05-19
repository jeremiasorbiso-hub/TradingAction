# models/rl_agent.py
"""
Deep Reinforcement Learning Agents for autonomous trading
- PPO (Proximal Policy Optimization): stable, SOTA for continuous control
- DQN (Deep Q-Networks): discrete action spaces
Uses Bellman equation: Q(s,a) = R(s,a) + γ max_a' Q(s',a')
"""
import numpy as np
import torch
import torch.nn as nn
from collections import deque
from typing import Tuple, Optional, Dict
from ..core.config import get_config

class ActorNetwork(nn.Module):
    """Policy network π(a|s) for continuous action space"""
    
    def __init__(self, state_dim: int, action_dim: int = 3,
                 hidden_dim: int = 256):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, action_dim)
        )
        
        # Log standard deviation (learnable exploration noise)
        self.log_std = nn.Parameter(torch.zeros(action_dim))
    
    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns: (action_mean, action_std)
        """
        mean = self.network(state)
        std = torch.exp(self.log_std)
        return mean, std
    
    def sample(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Sample action from policy"""
        mean, std = self.forward(state)
        normal = torch.distributions.Normal(mean, std)
        action = normal.rsample()
        log_prob = normal.log_prob(action).sum(dim=-1, keepdim=True)
        
        # Tanh squashing for bounded actions
        action = torch.tanh(action)
        
        return action, log_prob

class CriticNetwork(nn.Module):
    """Value network V(s) for state evaluation"""
    
    def __init__(self, state_dim: int, hidden_dim: int = 256):
        super().__init__()
        
        self.network = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 1)
        )
    
    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """Returns value estimate V(s)"""
        return self.network(state)

class PPOAgent:
    """Proximal Policy Optimization agent
    
    State: [price, volatility, order_flow, position, account_equity, momentum]
    Actions: [-1, 0, 1] mapped to [sell, hold, buy] with continuous intensity
    Reward: Sharpe ratio of returns
    """
    
    def __init__(self, state_dim: int = 6, action_dim: int = 3,
                 learning_rate: float = 3e-4, gamma: float = 0.99,
                 gae_lambda: float = 0.95, clip_ratio: float = 0.2):
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_ratio = clip_ratio
        
        self.actor = ActorNetwork(state_dim, action_dim)
        self.critic = CriticNetwork(state_dim)
        
        self.actor_optimizer = torch.optim.Adam(self.actor.parameters(), lr=learning_rate)
        self.critic_optimizer = torch.optim.Adam(self.critic.parameters(), lr=learning_rate)
        
        self.memory = deque(maxlen=2048)
        self.config = get_config()
        
        if self.config.cuda.enabled:
            self.actor.to(self.config.cuda.device)
            self.critic.to(self.config.cuda.device)
    
    def select_action(self, state: np.ndarray) -> Tuple[np.ndarray, float]:
        """Select trading action from state"""
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        
        if self.config.cuda.enabled:
            state_tensor = state_tensor.to(self.config.cuda.device)
        
        with torch.no_grad():
            action, log_prob = self.actor.sample(state_tensor)
        
        return action.cpu().numpy()[0], log_prob.item()
    
    def compute_gae(self, rewards: list, values: list, dones: list) -> Tuple[np.ndarray, np.ndarray]:
        """Compute Generalized Advantage Estimation"""
        advantages = []
        gae = 0
        
        for t in reversed(range(len(rewards))):
            if t == len(rewards) - 1:
                next_value = 0
            else:
                next_value = values[t + 1]
            
            delta = rewards[t] + self.gamma * next_value * (1 - dones[t]) - values[t]
            gae = delta + self.gamma * self.gae_lambda * (1 - dones[t]) * gae
            advantages.insert(0, gae)
        
        returns = np.array(advantages) + np.array(values)
        advantages = np.array(advantages)
        
        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        
        return advantages, returns
    
    def update(self, states: np.ndarray, actions: np.ndarray,
               rewards: list, dones: list, num_epochs: int = 3):
        """Update policy and value networks"""
        
        # Compute advantages
        with torch.no_grad():
            state_tensor = torch.FloatTensor(states)
            if self.config.cuda.enabled:
                state_tensor = state_tensor.to(self.config.cuda.device)
            values = self.critic(state_tensor).cpu().numpy().flatten()
        
        advantages, returns = self.compute_gae(rewards, values.tolist(), dones)
        
        for epoch in range(num_epochs):
            state_tensor = torch.FloatTensor(states)
            action_tensor = torch.FloatTensor(actions)
            advantage_tensor = torch.FloatTensor(advantages).unsqueeze(1)
            return_tensor = torch.FloatTensor(returns).unsqueeze(1)
            
            if self.config.cuda.enabled:
                state_tensor = state_tensor.to(self.config.cuda.device)
                action_tensor = action_tensor.to(self.config.cuda.device)
                advantage_tensor = advantage_tensor.to(self.config.cuda.device)
                return_tensor = return_tensor.to(self.config.cuda.device)
            
            # Actor update
            mean, std = self.actor.forward(state_tensor)
            normal = torch.distributions.Normal(mean, std)
            log_prob = normal.log_prob(action_tensor).sum(dim=-1, keepdim=True)
            
            ratio = torch.exp(log_prob)
            clipped_ratio = torch.clamp(ratio, 1 - self.clip_ratio, 1 + self.clip_ratio)
            loss_actor = -torch.min(ratio * advantage_tensor, clipped_ratio * advantage_tensor).mean()
            
            self.actor_optimizer.zero_grad()
            loss_actor.backward()
            self.actor_optimizer.step()
            
            # Critic update
            value_pred = self.critic(state_tensor)
            loss_critic = nn.MSELoss()(value_pred, return_tensor)
            
            self.critic_optimizer.zero_grad()
            loss_critic.backward()
            self.critic_optimizer.step()

class DQNAgent:
    """Deep Q-Network for discrete action space [SELL, HOLD, BUY]"""
    
    def __init__(self, state_dim: int = 6, action_dim: int = 3,
                 learning_rate: float = 1e-4, gamma: float = 0.99):
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.epsilon = 1.0
        self.epsilon_decay = 0.995
        self.epsilon_min = 0.01
        
        self.q_network = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, action_dim)
        )
        
        self.target_network = nn.Sequential(
            nn.Linear(state_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, action_dim)
        )
        
        self.optimizer = torch.optim.Adam(self.q_network.parameters(), lr=learning_rate)
        self.memory = deque(maxlen=10000)
        self.config = get_config()
        
        if self.config.cuda.enabled:
            self.q_network.to(self.config.cuda.device)
            self.target_network.to(self.config.cuda.device)
    
    def select_action(self, state: np.ndarray) -> int:
        """ε-greedy action selection"""
        if np.random.random() < self.epsilon:
            return np.random.randint(self.action_dim)
        
        state_tensor = torch.FloatTensor(state).unsqueeze(0)
        if self.config.cuda.enabled:
            state_tensor = state_tensor.to(self.config.cuda.device)
        
        with torch.no_grad():
            q_values = self.q_network(state_tensor)
        
        return q_values.cpu().argmax(dim=1).item()
    
    def update(self, batch_size: int = 32):
        """Update Q-network from experience replay"""
        if len(self.memory) < batch_size:
            return
        
        # Sample batch
        indices = np.random.choice(len(self.memory), batch_size)
        batch = [self.memory[i] for i in indices]
        
        states = torch.FloatTensor(np.array([b[0] for b in batch]))
        actions = torch.LongTensor(np.array([b[1] for b in batch]))
        rewards = torch.FloatTensor(np.array([b[2] for b in batch]))
        next_states = torch.FloatTensor(np.array([b[3] for b in batch]))
        dones = torch.FloatTensor(np.array([b[4] for b in batch]))
        
        if self.config.cuda.enabled:
            states = states.to(self.config.cuda.device)
            actions = actions.to(self.config.cuda.device)
            rewards = rewards.to(self.config.cuda.device)
            next_states = next_states.to(self.config.cuda.device)
            dones = dones.to(self.config.cuda.device)
        
        # Compute target Q-values
        with torch.no_grad():
            next_q_values = self.target_network(next_states).max(dim=1)[0]
            target_q = rewards + self.gamma * next_q_values * (1 - dones)
        
        # Compute loss
        q_values = self.q_network(states).gather(1, actions.unsqueeze(1))
        loss = nn.MSELoss()(q_values, target_q.unsqueeze(1))
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        # Update epsilon
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

class DRLAgent(PPOAgent):
    """Wrapper for Deep RL trading agent (uses PPO by default)"""
    pass
