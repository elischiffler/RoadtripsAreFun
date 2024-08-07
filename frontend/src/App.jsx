import React from "react";
import "./App.css";
import { Routes } from "./Routes";

function App() {
  
  const isAuthenticated = () => {
    const accessToken = sessionStorage.getItem('accessToken');
    return !!accessToken;
  };
  return (
    <div>
      <Routes />
    </div>
  );
}

export default App;
