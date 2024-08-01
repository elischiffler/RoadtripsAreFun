import React, { useState } from "react";
import LoginPage, {
  Logo,
  Banner,
  Footer,
  Username,
  Password,
} from "@react-login-page/page11";
import LogoButton from "../components/LogoButton";
import LoginBannerBgImg from "../assets/LoginBanner.jpg";
import VisibilityIcon from "@mui/icons-material/Visibility";
import VisibilityOffIcon from "@mui/icons-material/VisibilityOff";

const Demo = () => {
  // State to manage password visibility
  const [showPassword, setShowPassword] = useState(false);

  // Toggle password visibility
  const handleTogglePasswordVisibility = () => {
    setShowPassword((prevShowPassword) => !prevShowPassword);
  };

  return (
    <LoginPage style={{ height: "100vh" }}>
      <Logo>
        <LogoButton />
      </Logo>
      <Username visible={true} />

      <div style={{ position: "relative", marginBottom: "20px" }}>
        <Password
          index={2}
          type={showPassword ? "text" : "password"}
          style={{ width: "100%", paddingRight: "40px" }} // Add padding to the right for the icon
        />
        <div
          style={{
            position: "absolute",
            right: "885px", // Adjust this value to position the icon properly
            top: "52.3%",
            transform: "translateY(-50%)",
            cursor: "pointer",
            zIndex: 1,
            display: "flex",
            alignItems: "center",
          }}
          onClick={handleTogglePasswordVisibility}
        >
          {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
        </div>
      </div>
      <Username
        keyname="checkbox"
        type="checkbox"
        index={3}
        placeholder="Remember Me"
        style={{ width: "auto" }}
      >
        <div
          style={{
            fontSize: 14,
            display: "flex",
            justifyContent: "space-between",
            flex: 1,
          }}
        >
          <div>Remember Me</div>
        </div>
      </Username>
      <Banner>
        <img src={LoginBannerBgImg} alt="banner" />
      </Banner>
      <Footer>
        <a
          href="#"
          onClick={(event) => event.preventDefault()}
          style={{ marginRight: "20px" }}
        >
          Forgot Password
        </a>
        <a href="#">Sign up now</a>
      </Footer>
    </LoginPage>
  );
};

export default Demo;
