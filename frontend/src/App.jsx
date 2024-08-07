import React from "react";
import "./App.css";
import { Routes } from "./Routes";

function App() {
  const isAuthenticated = () => {
    //For use later to change screen if user is logged in
    const accessToken = sessionStorage.getItem("accessToken");
    return !!accessToken;
  };

  return (
    <div>
      <Routes />
    </div>
  );
}

export default App;
